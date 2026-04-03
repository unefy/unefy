import json
import uuid
from collections.abc import AsyncGenerator

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_db_session
from app.models import Base, Tenant
from app.models.user import TenantMembership, User


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Override with TEST_DATABASE_URL env var or testcontainers in CI."""
    import os

    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://unefy:unefy@localhost:5432/unefy_test",
    )


@pytest.fixture
async def db_engine(test_db_url: str):  # type: ignore[no-untyped-def]
    engine = create_async_engine(test_db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession]:  # type: ignore[no-untyped-def, type-arg]
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def fake_redis():  # type: ignore[no-untyped-def]
    """Create a fakeredis instance for testing."""
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


@pytest.fixture
async def test_tenant(db_session: AsyncSession) -> Tenant:
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Test Club",
        slug="test-club",
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user without any tenant membership."""
    user = User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        name="Test User",
        image=None,
        email_verified=True,
        google_id="google-test-id-123",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def test_membership(
    db_session: AsyncSession, test_user: User, test_tenant: Tenant
) -> TenantMembership:
    """Create a tenant membership linking test_user to test_tenant as owner."""
    membership = TenantMembership(
        id=uuid.uuid4(),
        user_id=test_user.id,
        tenant_id=test_tenant.id,
        role="owner",
        is_active=True,
    )
    db_session.add(membership)
    await db_session.flush()
    return membership


@pytest.fixture
async def client(db_session: AsyncSession, fake_redis) -> AsyncGenerator[AsyncClient]:  # type: ignore[no-untyped-def, type-arg]
    """Unauthenticated client with DB and Redis overrides."""
    import app.redis as redis_module
    from app.main import app

    async def override_db() -> AsyncGenerator[AsyncSession]:  # type: ignore[type-arg]
        yield db_session

    # Override DB dependency
    app.dependency_overrides[get_db_session] = override_db

    # Inject fake redis at module level
    original_redis = redis_module._redis_client
    redis_module._redis_client = fake_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    redis_module._redis_client = original_redis
    app.dependency_overrides.clear()


@pytest.fixture
async def anon_client(client: AsyncClient) -> AsyncClient:
    """Unauthenticated client — alias for clarity."""
    return client


@pytest.fixture
async def auth_client(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> AsyncGenerator[AsyncClient]:  # type: ignore[type-arg]
    """Authenticated client with a valid session cookie (owner of test_tenant)."""
    import app.redis as redis_module
    from app.main import app

    async def override_db() -> AsyncGenerator[AsyncSession]:  # type: ignore[type-arg]
        yield db_session

    app.dependency_overrides[get_db_session] = override_db

    original_redis = redis_module._redis_client
    redis_module._redis_client = fake_redis

    # Create a real session in fake Redis
    session_token = uuid.uuid4().hex
    session_data = json.dumps(
        {
            "user_id": str(test_user.id),
            "tenant_id": str(test_tenant.id),
            "role": "owner",
        }
    )
    await fake_redis.set(f"session:{session_token}", session_data, ex=604800)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"unefy_session": session_token},
    ) as ac:
        yield ac

    redis_module._redis_client = original_redis
    app.dependency_overrides.clear()


@pytest.fixture
async def onboarding_client(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_user: User,
) -> AsyncGenerator[AsyncClient]:  # type: ignore[type-arg]
    """Authenticated client with session but NO tenant (onboarding state)."""
    import app.redis as redis_module
    from app.main import app

    async def override_db() -> AsyncGenerator[AsyncSession]:  # type: ignore[type-arg]
        yield db_session

    app.dependency_overrides[get_db_session] = override_db

    original_redis = redis_module._redis_client
    redis_module._redis_client = fake_redis

    session_token = uuid.uuid4().hex
    session_data = json.dumps(
        {
            "user_id": str(test_user.id),
            "tenant_id": None,
            "role": None,
        }
    )
    await fake_redis.set(f"session:{session_token}", session_data, ex=604800)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"unefy_session": session_token},
    ) as ac:
        yield ac

    redis_module._redis_client = original_redis
    app.dependency_overrides.clear()
