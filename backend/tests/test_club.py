import json
import uuid
from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User

# --- GET /api/v1/club ---


async def test_get_club_authenticated(
    auth_client: AsyncClient,
    test_tenant: Tenant,
) -> None:
    """Authenticated owner can fetch their club details."""
    response = await auth_client.get("/api/v1/club")
    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert data["id"] == str(test_tenant.id)
    assert data["name"] == test_tenant.name
    assert data["slug"] == test_tenant.slug


async def test_get_club_unauthenticated(anon_client: AsyncClient) -> None:
    """Unauthenticated request to GET /club returns 403."""
    response = await anon_client.get("/api/v1/club")
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "FORBIDDEN"


async def test_get_club_returns_all_fields(
    auth_client: AsyncClient,
    test_tenant: Tenant,
    db_session: AsyncSession,
) -> None:
    """Club response includes all expected fields."""
    # Update tenant with extra data
    test_tenant.email = "club@example.com"
    test_tenant.phone = "+49123456789"
    test_tenant.city = "Berlin"
    test_tenant.country = "DE"
    test_tenant.is_nonprofit = True
    await db_session.flush()

    response = await auth_client.get("/api/v1/club")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["email"] == "club@example.com"
    assert data["phone"] == "+49123456789"
    assert data["city"] == "Berlin"
    assert data["country"] == "DE"
    assert data["is_nonprofit"] is True


# --- PATCH /api/v1/club ---


async def test_update_club_owner(
    auth_client: AsyncClient,
    test_tenant: Tenant,
) -> None:
    """Owner can update club details."""
    response = await auth_client.patch(
        "/api/v1/club",
        json={"name": "Updated Club Name", "city": "Munich"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Updated Club Name"
    assert data["city"] == "Munich"


async def test_update_club_admin_role(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
) -> None:
    """Admin can also update club details."""
    import app.redis as redis_module
    from app.main import app

    # Create an admin user
    admin_user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        name="Admin User",
        email_verified=True,
    )
    db_session.add(admin_user)
    await db_session.flush()

    membership = TenantMembership(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        tenant_id=test_tenant.id,
        role="admin",
        is_active=True,
    )
    db_session.add(membership)
    await db_session.flush()

    async def override_db() -> AsyncGenerator[AsyncSession]:  # type: ignore[type-arg]
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    original_redis = redis_module._redis_client
    redis_module._redis_client = fake_redis

    session_token = uuid.uuid4().hex
    session_data = json.dumps(
        {
            "user_id": str(admin_user.id),
            "tenant_id": str(test_tenant.id),
            "role": "admin",
        }
    )
    await fake_redis.set(f"session:{session_token}", session_data, ex=604800)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"unefy_session": session_token},
    ) as ac:
        response = await ac.patch(
            "/api/v1/club",
            json={"name": "Admin Updated Club"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Admin Updated Club"

    redis_module._redis_client = original_redis
    app.dependency_overrides.clear()


async def test_update_club_validates_email_format(
    auth_client: AsyncClient,
) -> None:
    """Invalid email format is rejected by Pydantic validation."""
    response = await auth_client.patch(
        "/api/v1/club",
        json={"email": "not-an-email"},
    )
    assert response.status_code == 422


async def test_update_club_validates_name_min_length(
    auth_client: AsyncClient,
) -> None:
    """Name with fewer than 2 chars is rejected."""
    response = await auth_client.patch(
        "/api/v1/club",
        json={"name": "A"},
    )
    assert response.status_code == 422


async def test_update_club_validates_name_max_length(
    auth_client: AsyncClient,
) -> None:
    """Name exceeding 255 chars is rejected."""
    response = await auth_client.patch(
        "/api/v1/club",
        json={"name": "X" * 256},
    )
    assert response.status_code == 422


async def test_update_club_validates_short_name_max_length(
    auth_client: AsyncClient,
) -> None:
    """Short name exceeding 50 chars is rejected."""
    response = await auth_client.patch(
        "/api/v1/club",
        json={"short_name": "X" * 51},
    )
    assert response.status_code == 422


async def test_update_club_fails_for_member_role(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
) -> None:
    """Member role cannot update club — requires owner or admin."""
    import app.redis as redis_module
    from app.main import app

    member_user = User(
        id=uuid.uuid4(),
        email="member@example.com",
        name="Member User",
        email_verified=True,
    )
    db_session.add(member_user)
    await db_session.flush()

    membership = TenantMembership(
        id=uuid.uuid4(),
        user_id=member_user.id,
        tenant_id=test_tenant.id,
        role="member",
        is_active=True,
    )
    db_session.add(membership)
    await db_session.flush()

    async def override_db() -> AsyncGenerator[AsyncSession]:  # type: ignore[type-arg]
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    original_redis = redis_module._redis_client
    redis_module._redis_client = fake_redis

    session_token = uuid.uuid4().hex
    session_data = json.dumps(
        {
            "user_id": str(member_user.id),
            "tenant_id": str(test_tenant.id),
            "role": "member",
        }
    )
    await fake_redis.set(f"session:{session_token}", session_data, ex=604800)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"unefy_session": session_token},
    ) as ac:
        response = await ac.patch(
            "/api/v1/club",
            json={"name": "Hacked Club Name"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"

    redis_module._redis_client = original_redis
    app.dependency_overrides.clear()


async def test_update_club_unauthenticated(anon_client: AsyncClient) -> None:
    """Unauthenticated request to PATCH /club returns 403."""
    response = await anon_client.patch(
        "/api/v1/club",
        json={"name": "No Auth Club"},
    )
    assert response.status_code == 403


# --- Tenant isolation ---


async def test_tenant_isolation(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
) -> None:
    """User from tenant A cannot see tenant B's club data."""
    import app.redis as redis_module
    from app.main import app

    # Create tenant B with its own user
    tenant_b = Tenant(
        id=uuid.uuid4(),
        name="Other Club",
        slug="other-club",
    )
    db_session.add(tenant_b)
    await db_session.flush()

    user_b = User(
        id=uuid.uuid4(),
        email="userb@example.com",
        name="User B",
        email_verified=True,
    )
    db_session.add(user_b)
    await db_session.flush()

    membership_b = TenantMembership(
        id=uuid.uuid4(),
        user_id=user_b.id,
        tenant_id=tenant_b.id,
        role="owner",
        is_active=True,
    )
    db_session.add(membership_b)
    await db_session.flush()

    async def override_db() -> AsyncGenerator[AsyncSession]:  # type: ignore[type-arg]
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    original_redis = redis_module._redis_client
    redis_module._redis_client = fake_redis

    # Create session for user B
    session_token = uuid.uuid4().hex
    session_data = json.dumps(
        {
            "user_id": str(user_b.id),
            "tenant_id": str(tenant_b.id),
            "role": "owner",
        }
    )
    await fake_redis.set(f"session:{session_token}", session_data, ex=604800)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"unefy_session": session_token},
    ) as ac:
        response = await ac.get("/api/v1/club")

    assert response.status_code == 200
    data = response.json()["data"]
    # User B should see their own club, not test_tenant
    assert data["id"] == str(tenant_b.id)
    assert data["name"] == "Other Club"
    assert data["id"] != str(test_tenant.id)

    redis_module._redis_client = original_redis
    app.dependency_overrides.clear()
