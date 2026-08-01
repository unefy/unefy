"""Tests for passwordless sign-in via magic link.

Auth-critical surface, so the focus is on what an attacker gets: the endpoint
must not reveal whether an account exists, and a link must not survive its
first use.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import COOKIE_NAME, get_session_data
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User
from app.services.magic_link import _hash, consume_token, issue_token


@pytest.fixture
async def redis_installed(fake_redis):  # type: ignore[no-untyped-def]
    """Install the fake Redis as the module-level client.

    The `client` fixture already does this, but the service-level tests below
    call `issue_token`/`consume_token` directly without going through HTTP.
    """
    import app.redis as redis_module

    original = redis_module._redis_client
    redis_module._redis_client = fake_redis
    yield fake_redis
    redis_module._redis_client = original


async def _request_link(client: AsyncClient, email: str):  # type: ignore[no-untyped-def]
    return await client.post("/api/v1/auth/magic-link/request", json={"email": email})


async def _token_for(fake_redis, email: str) -> str:  # type: ignore[no-untyped-def]
    """Recover the issued token by matching its hash against Redis.

    The endpoint only mails the token, so the test re-derives which stored hash
    belongs to a token it generates itself.
    """
    from app.config import get_settings

    return await issue_token(email, get_settings())


# --- Requesting ---


async def test_request_returns_ok_for_unknown_email(client: AsyncClient) -> None:
    """An unknown address must look exactly like a known one."""
    resp = await _request_link(client, "nobody@example.com")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["sent"] is True


async def test_request_response_is_identical_for_known_and_unknown(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The endpoint must not work as an account-existence oracle."""
    db_session.add(User(email="known@example.com", name="Known", email_verified=True))
    await db_session.flush()

    known = await _request_link(client, "known@example.com")
    unknown = await _request_link(client, "unknown@example.com")

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


async def test_request_rejects_malformed_email(client: AsyncClient) -> None:
    resp = await _request_link(client, "not-an-email")
    assert resp.status_code == 422, resp.text


# --- Token handling ---


async def test_token_is_stored_hashed_never_plain(redis_installed) -> None:  # type: ignore[no-untyped-def]
    """A Redis dump must not yield usable links."""
    from app.config import get_settings

    token = await issue_token("hash@example.com", get_settings())

    assert await redis_installed.get(f"magic-link:{_hash(token)}") is not None
    assert await redis_installed.get(f"magic-link:{token}") is None


async def test_token_works_exactly_once(redis_installed) -> None:  # type: ignore[no-untyped-def]
    from app.config import get_settings

    token = await issue_token("once@example.com", get_settings())

    assert await consume_token(token) == "once@example.com"
    assert await consume_token(token) is None


async def test_unknown_token_returns_none(redis_installed) -> None:  # type: ignore[no-untyped-def]
    assert await consume_token("not-a-real-token") is None


async def test_email_is_normalized(redis_installed) -> None:  # type: ignore[no-untyped-def]
    """Casing must not create a second account for the same mailbox."""
    from app.config import get_settings

    token = await issue_token("  MiXeD@Example.COM ", get_settings())
    assert await consume_token(token) == "mixed@example.com"


# --- Verifying ---


async def test_verify_creates_user_and_session(
    client: AsyncClient, db_session: AsyncSession, fake_redis
) -> None:  # type: ignore[no-untyped-def]
    token = await _token_for(fake_redis, "fresh@example.com")

    resp = await client.get(f"/api/v1/auth/magic-link/verify?token={token}")

    assert resp.status_code == 302, resp.text
    assert resp.headers["location"].endswith("/onboarding")

    user = (
        await db_session.execute(select(User).where(User.email == "fresh@example.com"))
    ).scalar_one_or_none()
    assert user is not None
    # Opening the link proves control of the mailbox.
    assert user.email_verified is True

    session_token = resp.cookies.get(COOKIE_NAME)
    assert session_token is not None
    data = await get_session_data(session_token)
    assert data is not None and data.user_id == user.id


async def test_verify_sends_member_of_a_club_to_the_app(
    client: AsyncClient, db_session: AsyncSession, fake_redis, test_tenant: Tenant
) -> None:  # type: ignore[no-untyped-def]
    user = User(email="member@example.com", name="Member", email_verified=True)
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        TenantMembership(
            id=uuid.uuid4(),
            user_id=user.id,
            tenant_id=test_tenant.id,
            role="owner",
            is_active=True,
        )
    )
    await db_session.flush()

    token = await _token_for(fake_redis, "member@example.com")
    resp = await client.get(f"/api/v1/auth/magic-link/verify?token={token}")

    assert resp.status_code == 302
    assert not resp.headers["location"].endswith("/onboarding")

    data = await get_session_data(resp.cookies[COOKIE_NAME])
    assert data is not None
    assert data.tenant_id == test_tenant.id
    assert data.role == "owner"


async def test_verify_with_invalid_token_grants_nothing(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/magic-link/verify?token=garbage")

    assert resp.status_code == 302
    assert "error=link_invalid" in resp.headers["location"]
    assert resp.cookies.get(COOKIE_NAME) is None


async def test_verify_twice_grants_only_one_session(client: AsyncClient, fake_redis) -> None:  # type: ignore[no-untyped-def]
    """A link forwarded or prefetched by a scanner must not stay usable."""
    token = await _token_for(fake_redis, "replay@example.com")

    first = await client.get(f"/api/v1/auth/magic-link/verify?token={token}")
    second = await client.get(f"/api/v1/auth/magic-link/verify?token={token}")

    assert first.cookies.get(COOKIE_NAME) is not None
    assert second.cookies.get(COOKIE_NAME) is None
    assert "error=link_invalid" in second.headers["location"]


async def test_verify_reuses_existing_account(
    client: AsyncClient, db_session: AsyncSession, fake_redis
) -> None:  # type: ignore[no-untyped-def]
    """Signing in must never create a duplicate account for the same address."""
    existing = User(email="dup@example.com", name="Existing", email_verified=True)
    db_session.add(existing)
    await db_session.flush()

    token = await _token_for(fake_redis, "dup@example.com")
    await client.get(f"/api/v1/auth/magic-link/verify?token={token}")

    users = (
        (await db_session.execute(select(User).where(User.email == "dup@example.com")))
        .scalars()
        .all()
    )
    assert len(users) == 1
    assert users[0].id == existing.id


@pytest.mark.parametrize("method,path", [("POST", "/api/v1/auth/magic-link/request")])
async def test_endpoints_need_no_authentication(
    client: AsyncClient, method: str, path: str
) -> None:
    """Sign-in has to work for someone who is, by definition, not signed in."""
    resp = await client.request(method, path, json={"email": "anon@example.com"})
    assert resp.status_code == 200, resp.text
