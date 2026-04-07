"""Mobile JWT auth endpoint tests.

Covers:
- POST /api/v1/auth/mobile/dev/login (happy path + guards)
- POST /api/v1/auth/mobile/refresh (rotation + revocation)
- POST /api/v1/auth/mobile/logout (idempotent revocation)
- Bearer-token authentication on a protected endpoint
- Tenant isolation when using Bearer tokens
"""

import uuid
from collections.abc import AsyncGenerator, Iterator
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.jwt import create_access_token, create_refresh_token
from app.database import get_db_session
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User

# --- Helpers ------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _ensure_debug_mode(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Most tests assume DEBUG=true. Tests that need DEBUG=false override."""
    get_settings.cache_clear()
    monkeypatch.setenv("DEBUG", "true")
    yield
    get_settings.cache_clear()


@pytest.fixture
async def mobile_client(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
) -> AsyncGenerator[AsyncClient]:
    """Unauthenticated client — mobile clients have no session cookie."""
    import app.redis as redis_module
    from app.main import app

    async def override_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    original_redis = redis_module._redis_client
    redis_module._redis_client = fake_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    redis_module._redis_client = original_redis
    app.dependency_overrides.clear()


# --- /dev/login ---------------------------------------------------------------


async def test_dev_login_returns_token_pair(
    mobile_client: AsyncClient,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    response = await mobile_client.post(
        "/api/v1/auth/mobile/dev/login",
        json={"email": test_user.email},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["access_expires_in"] == 900
    assert data["user"]["id"] == str(test_user.id)
    assert data["user"]["email"] == test_user.email
    assert data["tenant"]["id"] == str(test_tenant.id)
    assert data["tenant"]["name"] == test_tenant.name
    assert data["role"] == "owner"


async def test_dev_login_user_without_membership_returns_412(
    mobile_client: AsyncClient,
    test_user: User,
) -> None:
    """User exists but has no active tenant membership."""
    response = await mobile_client.post(
        "/api/v1/auth/mobile/dev/login",
        json={"email": test_user.email},
    )
    assert response.status_code == 412
    assert response.json()["error"]["code"] == "PRECONDITION_FAILED"


async def test_dev_login_unknown_email_returns_404(
    mobile_client: AsyncClient,
) -> None:
    response = await mobile_client.post(
        "/api/v1/auth/mobile/dev/login",
        json={"email": "ghost@example.com"},
    )
    assert response.status_code == 404


async def test_dev_login_disabled_when_not_debug(
    mobile_client: AsyncClient,
    test_user: User,
    test_membership: TenantMembership,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEBUG", "false")
    # Real secrets required when DEBUG=false
    long_secret = "x" * 64
    monkeypatch.setenv("INTERNAL_API_SECRET", long_secret)
    monkeypatch.setenv("SESSION_SECRET", long_secret)
    monkeypatch.setenv("JWT_SECRET", long_secret)
    get_settings.cache_clear()

    response = await mobile_client.post(
        "/api/v1/auth/mobile/dev/login",
        json={"email": test_user.email},
    )
    assert response.status_code == 404


async def test_dev_login_validates_email(mobile_client: AsyncClient) -> None:
    response = await mobile_client.post(
        "/api/v1/auth/mobile/dev/login",
        json={"email": "not-an-email"},
    )
    assert response.status_code == 422


# --- /refresh -----------------------------------------------------------------


async def test_refresh_rotates_tokens(
    mobile_client: AsyncClient,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    login = await mobile_client.post(
        "/api/v1/auth/mobile/dev/login",
        json={"email": test_user.email},
    )
    original = login.json()["data"]

    refresh_response = await mobile_client.post(
        "/api/v1/auth/mobile/refresh",
        json={"refresh_token": original["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    new_pair = refresh_response.json()["data"]
    assert new_pair["access_token"] != original["access_token"]
    assert new_pair["refresh_token"] != original["refresh_token"]

    # Old refresh token must no longer work after rotation.
    replay = await mobile_client.post(
        "/api/v1/auth/mobile/refresh",
        json={"refresh_token": original["refresh_token"]},
    )
    assert replay.status_code == 403
    assert replay.json()["error"]["code"] == "FORBIDDEN"


async def test_refresh_with_bogus_token(mobile_client: AsyncClient) -> None:
    response = await mobile_client.post(
        "/api/v1/auth/mobile/refresh",
        json={"refresh_token": "not.a.jwt"},
    )
    assert response.status_code == 403


async def test_refresh_rejects_access_token(
    mobile_client: AsyncClient,
    test_user: User,
) -> None:
    """Passing an access token to /refresh must be rejected."""
    access, _ = create_access_token(
        user_id=test_user.id,
        tenant_id=uuid.uuid4(),
        role="owner",
    )
    response = await mobile_client.post(
        "/api/v1/auth/mobile/refresh",
        json={"refresh_token": access},
    )
    assert response.status_code == 403


async def test_refresh_with_unknown_jti(
    mobile_client: AsyncClient,
    test_user: User,
) -> None:
    """A valid-signature refresh token whose jti isn't in Redis is rejected."""
    refresh_token, _ = create_refresh_token(user_id=test_user.id)
    response = await mobile_client.post(
        "/api/v1/auth/mobile/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 403


# --- /logout ------------------------------------------------------------------


async def test_logout_revokes_refresh_token(
    mobile_client: AsyncClient,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    login = await mobile_client.post(
        "/api/v1/auth/mobile/dev/login",
        json={"email": test_user.email},
    )
    refresh_token = login.json()["data"]["refresh_token"]

    logout = await mobile_client.post(
        "/api/v1/auth/mobile/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout.status_code == 200

    # Refresh must fail after logout
    after = await mobile_client.post(
        "/api/v1/auth/mobile/refresh",
        json={"refresh_token": refresh_token},
    )
    assert after.status_code == 403


async def test_logout_is_idempotent_for_bad_token(mobile_client: AsyncClient) -> None:
    response = await mobile_client.post(
        "/api/v1/auth/mobile/logout",
        json={"refresh_token": "garbage"},
    )
    assert response.status_code == 200


# --- Bearer auth on protected endpoints ---------------------------------------


async def test_bearer_token_grants_access_to_members(
    mobile_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    # Seed one member in the tenant so we get a deterministic list response.
    member = Member(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        member_number="001",
        first_name="Alice",
        last_name="Example",
        joined_at=date(2024, 1, 1),
        status="active",
    )
    db_session.add(member)
    await db_session.flush()

    access, _ = create_access_token(
        user_id=test_user.id,
        tenant_id=test_tenant.id,
        role="owner",
    )

    response = await mobile_client.get(
        "/api/v1/members",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["first_name"] == "Alice"


async def test_bearer_token_with_inactive_membership_rejected(
    mobile_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    access, _ = create_access_token(
        user_id=test_user.id,
        tenant_id=test_tenant.id,
        role="owner",
    )

    # Revoke membership after token was issued.
    test_membership.is_active = False
    await db_session.flush()

    response = await mobile_client.get(
        "/api/v1/members",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


async def test_bearer_token_with_wrong_tenant_rejected(
    mobile_client: AsyncClient,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    """Token for a tenant the user does not belong to must be rejected."""
    other_tenant_id = uuid.uuid4()
    access, _ = create_access_token(
        user_id=test_user.id,
        tenant_id=other_tenant_id,
        role="owner",
    )
    response = await mobile_client.get(
        "/api/v1/members",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 401


async def test_garbage_bearer_token_rejected(mobile_client: AsyncClient) -> None:
    response = await mobile_client.get(
        "/api/v1/members",
        headers={"Authorization": "Bearer nonsense.not.jwt"},
    )
    assert response.status_code == 401


async def test_refresh_token_cannot_be_used_as_access_token(
    mobile_client: AsyncClient,
    test_user: User,
) -> None:
    refresh_token, _ = create_refresh_token(user_id=test_user.id)
    response = await mobile_client.get(
        "/api/v1/members",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert response.status_code == 401
