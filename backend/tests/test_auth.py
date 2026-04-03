import json
import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User

# --- GET /api/v1/auth/me ---


async def test_me_with_valid_session(
    auth_client: AsyncClient,
    test_user: User,
    test_tenant: Tenant,
) -> None:
    """Authenticated user gets their profile with tenant context."""
    response = await auth_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert data is not None
    assert data["user"]["id"] == str(test_user.id)
    assert data["user"]["name"] == test_user.name
    assert data["user"]["email"] == test_user.email
    assert data["tenant_id"] == str(test_tenant.id)
    assert data["tenant_name"] == test_tenant.name
    assert data["role"] == "owner"
    assert data["needs_onboarding"] is False


async def test_me_without_session(anon_client: AsyncClient) -> None:
    """Unauthenticated request returns data: null."""
    response = await anon_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json() == {"data": None}


async def test_me_with_invalid_session(anon_client: AsyncClient) -> None:
    """Request with a bogus session cookie returns data: null."""
    response = await anon_client.get(
        "/api/v1/auth/me",
        cookies={"unefy_session": "invalid-token-that-does-not-exist"},
    )
    assert response.status_code == 200
    assert response.json() == {"data": None}


async def test_me_onboarding_user(
    onboarding_client: AsyncClient,
    test_user: User,
) -> None:
    """User in onboarding state (no tenant) sees needs_onboarding=True."""
    response = await onboarding_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert data is not None
    assert data["user"]["id"] == str(test_user.id)
    assert data["tenant_id"] is None
    assert data["needs_onboarding"] is True


# --- POST /api/v1/auth/onboarding/create-club ---


async def test_create_club_success(
    onboarding_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Authenticated user without a tenant can create a club."""
    response = await onboarding_client.post(
        "/api/v1/auth/onboarding/create-club",
        json={"club_name": "My New Club"},
    )
    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert data["name"] == "My New Club"
    assert "tenant_id" in data
    assert data["slug"].startswith("club-")

    # Verify tenant was created in DB
    tenant_id = uuid.UUID(data["tenant_id"])
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    result = await db_session.execute(stmt)
    tenant = result.scalar_one_or_none()
    assert tenant is not None
    assert tenant.name == "My New Club"

    # Verify membership was created
    stmt = select(TenantMembership).where(
        TenantMembership.user_id == test_user.id,
        TenantMembership.tenant_id == tenant_id,
    )
    result = await db_session.execute(stmt)
    membership = result.scalar_one_or_none()
    assert membership is not None
    assert membership.role == "owner"


async def test_create_club_fails_without_auth(anon_client: AsyncClient) -> None:
    """Unauthenticated request to create-club returns 403."""
    response = await anon_client.post(
        "/api/v1/auth/onboarding/create-club",
        json={"club_name": "Unauthorized Club"},
    )
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "FORBIDDEN"


async def test_create_club_fails_with_empty_name(
    onboarding_client: AsyncClient,
) -> None:
    """Empty club_name fails validation (min_length=2)."""
    response = await onboarding_client.post(
        "/api/v1/auth/onboarding/create-club",
        json={"club_name": ""},
    )
    assert response.status_code == 422


async def test_create_club_fails_with_short_name(
    onboarding_client: AsyncClient,
) -> None:
    """Single-char club_name fails validation (min_length=2)."""
    response = await onboarding_client.post(
        "/api/v1/auth/onboarding/create-club",
        json={"club_name": "A"},
    )
    assert response.status_code == 422


async def test_create_club_fails_if_user_already_has_tenant(
    auth_client: AsyncClient,
    test_membership: TenantMembership,
) -> None:
    """User who already has a tenant gets 409 Conflict."""
    response = await auth_client.post(
        "/api/v1/auth/onboarding/create-club",
        json={"club_name": "Second Club"},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "CONFLICT"


# --- POST /api/v1/auth/logout ---


async def test_logout_clears_session(
    fake_redis,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    """Logout deletes the Redis session and clears the cookie."""
    from collections.abc import AsyncGenerator

    from httpx import ASGITransport

    import app.redis as redis_module
    from app.main import app

    async def override_db() -> AsyncGenerator[AsyncSession]:  # type: ignore[type-arg]
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    original_redis = redis_module._redis_client
    redis_module._redis_client = fake_redis

    # Create a session
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
        response = await ac.post("/api/v1/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"data": {"message": "Logged out"}}

    # Session should be deleted from Redis
    raw = await fake_redis.get(f"session:{session_token}")
    assert raw is None

    redis_module._redis_client = original_redis
    app.dependency_overrides.clear()


async def test_logout_without_session(anon_client: AsyncClient) -> None:
    """Logout without a session still returns 200."""
    response = await anon_client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"data": {"message": "Logged out"}}
