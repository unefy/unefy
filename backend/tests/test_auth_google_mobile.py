"""Google sign-in from the mobile app — ID token in, JWT pair out.

The tokens here are minted with a throwaway RSA key and Google's key endpoint
is stubbed with the matching public key, so the real verification path runs:
signature, issuer, audience, expiry and nonce are all checked by the code
under test rather than mocked away.
"""

import time
import uuid
from collections.abc import AsyncGenerator, Iterator
from typing import Any

import pytest
import respx
from authlib.jose import JsonWebKey, JsonWebToken
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db_session
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User
from app.services import google_identity

CLIENT_ID = "test-server-client-id.apps.googleusercontent.com"
NONCE_URL = "/api/v1/auth/mobile/oauth/google/nonce"
SIGNIN_URL = "/api/v1/auth/mobile/oauth/google"

_jwt = JsonWebToken(["RS256"])

# One key for the whole module: generating RSA keys is slow, and every test
# that needs a *wrong* key gets its own below.
_signing_key = JsonWebKey.generate_key("RSA", 2048, is_private=True)


def _jwks(key: Any = None, kid: str = "test-key") -> dict[str, Any]:
    public = (key or _signing_key).as_dict(is_private=False)
    public.update(kid=kid, alg="RS256", use="sig")
    return {"keys": [public]}


def _id_token(
    *,
    nonce: str,
    email: str = "google-user@example.com",
    subject: str = "google-sub-1",
    email_verified: bool = True,
    audience: str = CLIENT_ID,
    issuer: str = "https://accounts.google.com",
    expires_in: int = 3600,
    key: Any = None,
    kid: str = "test-key",
    name: str | None = "Google User",
) -> str:
    now = int(time.time())
    claims = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "email": email,
        "email_verified": email_verified,
        "iat": now,
        "exp": now + expires_in,
        "nonce": nonce,
    }
    if name:
        claims["name"] = name
    token: bytes = _jwt.encode({"alg": "RS256", "kid": kid}, claims, key or _signing_key)
    return token.decode()


@pytest.fixture(autouse=True)
def _google_configured(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    get_settings.cache_clear()
    monkeypatch.setenv("GOOGLE_CLIENT_ID", CLIENT_ID)
    google_identity.reset_certs_cache()
    yield
    google_identity.reset_certs_cache()
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _google_certs() -> Iterator[respx.MockRouter]:
    """Google's key endpoint, answering with our throwaway public key."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(google_identity.GOOGLE_CERTS_URL).mock(
            return_value=Response(200, json=_jwks(), headers={"cache-control": "max-age=3600"}),
        )
        yield mock


@pytest.fixture
async def mobile_client(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
) -> AsyncGenerator[AsyncClient]:
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


async def _nonce(client: AsyncClient) -> str:
    response = await client.post(NONCE_URL)
    assert response.status_code == 200
    nonce: str = response.json()["data"]["nonce"]
    return nonce


# --- Nonce --------------------------------------------------------------------


async def test_nonce_is_single_use(
    mobile_client: AsyncClient,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    nonce = await _nonce(mobile_client)
    body = {"id_token": _id_token(nonce=nonce, email=test_user.email), "nonce": nonce}

    first = await mobile_client.post(SIGNIN_URL, json=body)
    assert first.status_code == 200

    # Same token, same nonce, second time: the account is real and the
    # signature still checks out, so only the spent nonce can stop this.
    replay = await mobile_client.post(SIGNIN_URL, json=body)
    assert replay.status_code == 403


async def test_unknown_nonce_is_rejected(mobile_client: AsyncClient) -> None:
    response = await mobile_client.post(
        SIGNIN_URL,
        json={"id_token": _id_token(nonce="never-issued"), "nonce": "never-issued"},
    )
    assert response.status_code == 403


async def test_token_nonce_must_match_the_issued_one(
    mobile_client: AsyncClient,
    test_user: User,
) -> None:
    """Two live nonces: the body names one, the token carries the other."""
    stolen = await _nonce(mobile_client)
    mine = await _nonce(mobile_client)

    response = await mobile_client.post(
        SIGNIN_URL,
        json={"id_token": _id_token(nonce=stolen, email=test_user.email), "nonce": mine},
    )
    assert response.status_code == 403


async def test_nonce_needs_configuration(
    mobile_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    response = await mobile_client.post(NONCE_URL)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "GOOGLE_NOT_CONFIGURED"


async def test_signin_needs_configuration(
    mobile_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nonce = await _nonce(mobile_client)
    get_settings.cache_clear()
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    response = await mobile_client.post(
        SIGNIN_URL,
        json={"id_token": _id_token(nonce=nonce), "nonce": nonce},
    )
    assert response.status_code == 503


# --- Happy paths --------------------------------------------------------------


async def test_signin_links_existing_account_and_returns_tokens(
    mobile_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    nonce = await _nonce(mobile_client)
    response = await mobile_client.post(
        SIGNIN_URL,
        json={"id_token": _id_token(nonce=nonce, email=test_user.email), "nonce": nonce},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["user"]["email"] == test_user.email
    assert data["tenant"]["id"] == str(test_tenant.id)

    await db_session.refresh(test_user)
    assert test_user.google_id == "google-sub-1"


async def test_returning_google_user_is_matched_by_subject(
    mobile_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    """The subject wins over the address — a renamed mailbox stays the same account."""
    user = User(
        email="old-address@example.com",
        name="Old Name",
        email_verified=True,
        google_id="google-sub-2",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        TenantMembership(user_id=user.id, tenant_id=test_tenant.id, role="member", is_active=True)
    )
    await db_session.flush()

    nonce = await _nonce(mobile_client)
    response = await mobile_client.post(
        SIGNIN_URL,
        json={
            "id_token": _id_token(
                nonce=nonce,
                subject="google-sub-2",
                email="new-address@example.com",
                name="New Name",
            ),
            "nonce": nonce,
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["user"]["id"] == str(user.id)
    await db_session.refresh(user)
    # The address is not taken from the token: changing it is an account
    # operation, not a side effect of signing in.
    assert user.email == "old-address@example.com"
    assert user.name == "New Name"


async def test_signin_without_club_reports_precondition_failed(
    mobile_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    nonce = await _nonce(mobile_client)
    response = await mobile_client.post(
        SIGNIN_URL,
        json={
            "id_token": _id_token(
                nonce=nonce,
                subject=f"google-sub-{uuid.uuid4()}",
                email=f"fresh-{uuid.uuid4()}@example.com",
            ),
            "nonce": nonce,
        },
    )

    assert response.status_code == 412
    # The account exists now — an invitation must be able to find it.
    created = (
        (await db_session.execute(select(User).where(User.google_id.is_not(None)))).scalars().all()
    )
    assert created


# --- Rejections ---------------------------------------------------------------


async def test_unverified_email_cannot_claim_an_existing_account(
    mobile_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    nonce = await _nonce(mobile_client)
    response = await mobile_client.post(
        SIGNIN_URL,
        json={
            "id_token": _id_token(nonce=nonce, email=test_user.email, email_verified=False),
            "nonce": nonce,
        },
    )

    assert response.status_code == 403
    await db_session.refresh(test_user)
    # Untouched — the unverified identity did not attach itself to the account.
    assert test_user.google_id != "google-sub-1"


async def test_foreign_audience_is_rejected(mobile_client: AsyncClient) -> None:
    nonce = await _nonce(mobile_client)
    response = await mobile_client.post(
        SIGNIN_URL,
        json={"id_token": _id_token(nonce=nonce, audience="some-other-app"), "nonce": nonce},
    )
    assert response.status_code == 403


async def test_extra_mobile_client_id_is_accepted(
    mobile_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """A self-hoster accepting the published app's client id."""
    get_settings.cache_clear()
    monkeypatch.setenv("GOOGLE_MOBILE_CLIENT_IDS", '["published-app-client-id"]')

    nonce = await _nonce(mobile_client)
    response = await mobile_client.post(
        SIGNIN_URL,
        json={
            "id_token": _id_token(
                nonce=nonce,
                audience="published-app-client-id",
                email=test_user.email,
            ),
            "nonce": nonce,
        },
    )
    assert response.status_code == 200


async def test_foreign_issuer_is_rejected(mobile_client: AsyncClient) -> None:
    nonce = await _nonce(mobile_client)
    response = await mobile_client.post(
        SIGNIN_URL,
        json={"id_token": _id_token(nonce=nonce, issuer="https://evil.example"), "nonce": nonce},
    )
    assert response.status_code == 403


async def test_expired_token_is_rejected(mobile_client: AsyncClient, test_user: User) -> None:
    nonce = await _nonce(mobile_client)
    response = await mobile_client.post(
        SIGNIN_URL,
        json={
            "id_token": _id_token(nonce=nonce, email=test_user.email, expires_in=-3600),
            "nonce": nonce,
        },
    )
    assert response.status_code == 403


async def test_token_signed_by_another_key_is_rejected(
    mobile_client: AsyncClient,
    test_user: User,
) -> None:
    """Right shape, right claims, wrong signer — the whole point of the check."""
    forged_key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    nonce = await _nonce(mobile_client)
    response = await mobile_client.post(
        SIGNIN_URL,
        json={
            "id_token": _id_token(nonce=nonce, email=test_user.email, key=forged_key),
            "nonce": nonce,
        },
    )
    assert response.status_code == 403


async def test_garbage_token_is_rejected(mobile_client: AsyncClient) -> None:
    nonce = await _nonce(mobile_client)
    response = await mobile_client.post(
        SIGNIN_URL,
        json={"id_token": "not.a.jwt", "nonce": nonce},
    )
    assert response.status_code == 403


async def test_token_without_email_is_rejected(mobile_client: AsyncClient) -> None:
    nonce = await _nonce(mobile_client)
    now = int(time.time())
    raw: bytes = _jwt.encode(
        {"alg": "RS256", "kid": "test-key"},
        {
            "iss": "https://accounts.google.com",
            "aud": CLIENT_ID,
            "sub": "google-sub-no-mail",
            "iat": now,
            "exp": now + 3600,
            "nonce": nonce,
        },
        _signing_key,
    )
    response = await mobile_client.post(
        SIGNIN_URL,
        json={"id_token": raw.decode(), "nonce": nonce},
    )
    assert response.status_code == 403


# --- Key handling -------------------------------------------------------------


async def test_unknown_key_id_triggers_one_refetch(
    mobile_client: AsyncClient,
    _google_certs: respx.MockRouter,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """A rotation we have not cached: refetch once, then accept."""
    rotated_key = JsonWebKey.generate_key("RSA", 2048, is_private=True)

    # First answer is the stale set — it does not contain the key that signed
    # the token. The second is what Google actually serves now.
    _google_certs.get(google_identity.GOOGLE_CERTS_URL).mock(
        side_effect=[
            Response(200, json=_jwks()),
            Response(200, json=_jwks(rotated_key, kid="test-key-2")),
        ],
    )

    nonce = await _nonce(mobile_client)
    response = await mobile_client.post(
        SIGNIN_URL,
        json={
            "id_token": _id_token(
                nonce=nonce,
                email=test_user.email,
                key=rotated_key,
                kid="test-key-2",
            ),
            "nonce": nonce,
        },
    )
    assert response.status_code == 200


async def test_forged_key_id_fails_after_the_refetch(
    mobile_client: AsyncClient,
    test_user: User,
) -> None:
    """The refetch is one retry, not an open invitation."""
    nonce = await _nonce(mobile_client)
    response = await mobile_client.post(
        SIGNIN_URL,
        json={
            "id_token": _id_token(nonce=nonce, email=test_user.email, kid="no-such-key"),
            "nonce": nonce,
        },
    )
    assert response.status_code == 403


async def test_key_endpoint_down_is_rejected_not_crashed(
    mobile_client: AsyncClient,
    _google_certs: respx.MockRouter,
) -> None:
    _google_certs.get(google_identity.GOOGLE_CERTS_URL).mock(return_value=Response(500))
    nonce = await _nonce(mobile_client)
    response = await mobile_client.post(
        SIGNIN_URL,
        json={"id_token": _id_token(nonce=nonce), "nonce": nonce},
    )
    assert response.status_code == 403
