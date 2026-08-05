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
    # All four, not three: on a machine without a .env (CI), a forgotten one
    # fails Settings validation instead of this test's actual assertion.
    monkeypatch.setenv("ATTENDANCE_SECRET", long_secret)
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


# --- /switch-tenant -------------------------------------------------------------


async def _second_membership(
    db_session: AsyncSession,
    user: User,
    *,
    role: str = "member",
    is_active: bool = True,
) -> Tenant:
    other = Tenant(id=uuid.uuid4(), name="Zweitverein", slug=f"zweit-{uuid.uuid4().hex[:6]}")
    db_session.add(other)
    await db_session.flush()
    db_session.add(
        TenantMembership(
            id=uuid.uuid4(),
            user_id=user.id,
            tenant_id=other.id,
            role=role,
            is_active=is_active,
        )
    )
    await db_session.flush()
    return other


async def test_switch_tenant_reissues_for_the_target_club(
    mobile_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    other = await _second_membership(db_session, test_user, role="member")
    login = await mobile_client.post(
        "/api/v1/auth/mobile/dev/login", json={"email": test_user.email}
    )
    access = login.json()["data"]["access_token"]

    response = await mobile_client.post(
        "/api/v1/auth/mobile/switch-tenant",
        json={"tenant_id": str(other.id)},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["tenant"]["id"] == str(other.id)
    # The role of the *target* club, not the one the caller arrived with.
    assert data["role"] == "member"
    assert data["access_token"] and data["refresh_token"]


async def test_switch_tenant_refuses_a_club_without_membership(
    mobile_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    stranger_club = Tenant(id=uuid.uuid4(), name="Fremd", slug=f"fremd-{uuid.uuid4().hex[:6]}")
    db_session.add(stranger_club)
    await db_session.flush()

    login = await mobile_client.post(
        "/api/v1/auth/mobile/dev/login", json={"email": test_user.email}
    )
    access = login.json()["data"]["access_token"]

    response = await mobile_client.post(
        "/api/v1/auth/mobile/switch-tenant",
        json={"tenant_id": str(stranger_club.id)},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 404


async def test_switch_tenant_refuses_an_inactive_membership(
    mobile_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    other = await _second_membership(db_session, test_user, is_active=False)

    login = await mobile_client.post(
        "/api/v1/auth/mobile/dev/login", json={"email": test_user.email}
    )
    access = login.json()["data"]["access_token"]

    response = await mobile_client.post(
        "/api/v1/auth/mobile/switch-tenant",
        json={"tenant_id": str(other.id)},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 404


async def test_switch_tenant_requires_authentication(
    mobile_client: AsyncClient, test_tenant: Tenant
) -> None:
    response = await mobile_client.post(
        "/api/v1/auth/mobile/switch-tenant",
        json={"tenant_id": str(test_tenant.id)},
    )
    assert response.status_code == 403


async def test_refresh_keeps_the_switched_tenant(
    mobile_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """The regression the tenant_id field exists for: without it a refresh
    silently re-pinned the session to the first membership."""
    other = await _second_membership(db_session, test_user)
    login = await mobile_client.post(
        "/api/v1/auth/mobile/dev/login", json={"email": test_user.email}
    )
    access = login.json()["data"]["access_token"]

    switched = await mobile_client.post(
        "/api/v1/auth/mobile/switch-tenant",
        json={"tenant_id": str(other.id)},
        headers={"Authorization": f"Bearer {access}"},
    )
    refresh_token = switched.json()["data"]["refresh_token"]

    refreshed = await mobile_client.post(
        "/api/v1/auth/mobile/refresh",
        json={"refresh_token": refresh_token, "tenant_id": str(other.id)},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["data"]["tenant"]["id"] == str(other.id)


async def test_refresh_falls_back_when_the_membership_is_gone(
    mobile_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    """A revoked membership must not brick the session — refresh falls back to
    the first active club instead of failing forever."""
    login = await mobile_client.post(
        "/api/v1/auth/mobile/dev/login", json={"email": test_user.email}
    )
    refresh_token = login.json()["data"]["refresh_token"]

    response = await mobile_client.post(
        "/api/v1/auth/mobile/refresh",
        json={"refresh_token": refresh_token, "tenant_id": str(uuid.uuid4())},
    )
    assert response.status_code == 200
    assert response.json()["data"]["tenant"]["id"] == str(test_tenant.id)


async def test_tenants_list_works_with_a_bearer_token(
    mobile_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    """The account menu's list: all clubs, the token's own marked current."""
    other = await _second_membership(db_session, test_user)
    login = await mobile_client.post(
        "/api/v1/auth/mobile/dev/login", json={"email": test_user.email}
    )
    access = login.json()["data"]["access_token"]

    response = await mobile_client.get(
        "/api/v1/auth/tenants",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 200, response.text
    rows = {row["tenant_id"]: row for row in response.json()["data"]}
    assert set(rows) == {str(test_tenant.id), str(other.id)}
    assert rows[str(test_tenant.id)]["is_current"] is True
    assert rows[str(other.id)]["is_current"] is False


# --- /magic-link (one-time code) ----------------------------------------------


async def _issue_code(email: str) -> str:
    """Self-issue a code like the magic-link tests self-issue tokens — the
    endpoint only ever mails it."""
    from app.services.magic_link import issue_otp

    return await issue_otp(email, get_settings())


async def _verify(client: AsyncClient, email: str, code: str):  # type: ignore[no-untyped-def]
    return await client.post(
        "/api/v1/auth/mobile/magic-link/verify", json={"email": email, "code": code}
    )


async def test_magic_request_is_flat_for_known_and_unknown(
    mobile_client: AsyncClient, db_session: AsyncSession
) -> None:
    """The request endpoint must not work as an account-existence oracle."""
    db_session.add(User(email="known-otp@example.com", name="Known", email_verified=True))
    await db_session.flush()

    known = await mobile_client.post(
        "/api/v1/auth/mobile/magic-link/request", json={"email": "known-otp@example.com"}
    )
    unknown = await mobile_client.post(
        "/api/v1/auth/mobile/magic-link/request", json={"email": "unknown-otp@example.com"}
    )

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {"data": {"sent": True}}


async def test_magic_verify_returns_token_pair_for_member(
    mobile_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    user = User(email="otp-member@example.com", name="OTP Member", email_verified=True)
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        TenantMembership(
            id=uuid.uuid4(),
            user_id=user.id,
            tenant_id=test_tenant.id,
            role="member",
            is_active=True,
        )
    )
    await db_session.flush()

    code = await _issue_code("otp-member@example.com")
    resp = await _verify(mobile_client, "otp-member@example.com", code)

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["access_token"] and data["refresh_token"]
    assert data["tenant"]["id"] == str(test_tenant.id)
    assert data["role"] == "member"


async def test_magic_verify_creates_the_user_but_412s_without_a_club(
    mobile_client: AsyncClient, db_session: AsyncSession
) -> None:
    """First login proves the mailbox; without a club there is no token to
    issue, and the app tells the person to ask for an invitation."""
    from sqlalchemy import select

    code = await _issue_code("fresh-otp@example.com")
    resp = await _verify(mobile_client, "fresh-otp@example.com", code)

    assert resp.status_code == 412, resp.text
    created = (
        await db_session.execute(select(User).where(User.email == "fresh-otp@example.com"))
    ).scalar_one()
    assert created.email_verified is True


async def test_magic_verify_rejects_a_wrong_code_but_allows_a_retry(
    mobile_client: AsyncClient,
) -> None:
    code = await _issue_code("retry-otp@example.com")

    typo = "000000" if code != "000000" else "000001"
    wrong = await _verify(mobile_client, "retry-otp@example.com", typo)
    assert wrong.status_code == 403

    right = await _verify(mobile_client, "retry-otp@example.com", code)
    # 412 (no club), not 403 — the code itself was accepted after the typo.
    assert right.status_code == 412, right.text


async def test_magic_verify_code_works_exactly_once(
    mobile_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    user = User(email="once-otp@example.com", name="Once", email_verified=True)
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        TenantMembership(
            id=uuid.uuid4(),
            user_id=user.id,
            tenant_id=test_tenant.id,
            role="member",
            is_active=True,
        )
    )
    await db_session.flush()

    code = await _issue_code("once-otp@example.com")
    assert (await _verify(mobile_client, "once-otp@example.com", code)).status_code == 200
    assert (await _verify(mobile_client, "once-otp@example.com", code)).status_code == 403


async def test_magic_verify_kills_the_code_after_too_many_guesses(
    mobile_client: AsyncClient,
) -> None:
    """Six digits only hold because guessing is capped: after the limit even
    the correct code must be dead."""
    from app.services.magic_link import OTP_MAX_ATTEMPTS

    code = await _issue_code("bruteforce-otp@example.com")
    wrong = "000000" if code != "000000" else "000001"

    for _ in range(OTP_MAX_ATTEMPTS):
        attempt = await _verify(mobile_client, "bruteforce-otp@example.com", wrong)
        assert attempt.status_code == 403

    assert (await _verify(mobile_client, "bruteforce-otp@example.com", code)).status_code == 403


async def test_magic_verify_without_a_requested_code_fails(
    mobile_client: AsyncClient,
) -> None:
    resp = await _verify(mobile_client, "never-requested@example.com", "123456")
    assert resp.status_code == 403


async def test_magic_verify_validates_the_code_shape(mobile_client: AsyncClient) -> None:
    for bad in ("12345", "1234567", "abcdef", ""):
        resp = await _verify(mobile_client, "shape@example.com", bad)
        assert resp.status_code == 422, bad


async def test_magic_flow_normalizes_the_address(
    mobile_client: AsyncClient,
) -> None:
    """Requesting with one casing and verifying with another is the same
    mailbox — people type their address, they do not paste it."""
    code = await _issue_code("MiXeD-OTP@Example.COM")
    resp = await _verify(mobile_client, "mixed-otp@example.com", code)
    assert resp.status_code == 412, resp.text  # code accepted; no club yet


async def test_a_new_request_replaces_the_previous_code(
    mobile_client: AsyncClient,
) -> None:
    first = await _issue_code("replace-otp@example.com")
    second = await _issue_code("replace-otp@example.com")

    if first != second:  # 1-in-a-million collision would make both valid
        assert (await _verify(mobile_client, "replace-otp@example.com", first)).status_code == 403
    assert (await _verify(mobile_client, "replace-otp@example.com", second)).status_code == 412
