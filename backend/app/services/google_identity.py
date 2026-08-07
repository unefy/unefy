"""Google identities: verifying an ID token and mapping it to an account.

Both sign-in paths end here, deliberately:

- **Web** goes through the redirect flow, where authlib does the code exchange
  and hands us the userinfo claims it already validated.
- **Mobile** never opens a browser. Android's Credential Manager returns a
  Google ID token signed for the *server* client id, which the app posts to
  the backend — so verification of that token is our job, not authlib's.

Keeping the account resolution in one function is the point: the rule that an
existing account may only be linked to a Google identity when Google attests
the address is verified has to hold on every path, and it stopped holding the
moment the mobile flow grew its own copy.
"""

import time
from dataclasses import dataclass
from typing import Any

import httpx
import structlog
from authlib.jose import JsonWebKey, JsonWebToken
from authlib.jose.errors import JoseError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.user import User

logger = structlog.get_logger()

# Both spellings appear in Google-issued tokens and both are legitimate.
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")

# The JWK set — RSA public keys, not the x509 certificates of the older
# endpoint. authlib picks the key by `kid` from the set.
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"

# Fallback when the response carries no usable Cache-Control. Google rotates
# roughly daily and publishes the successor well in advance, so an hour is
# short enough to pick a rotation up and long enough to not hammer them.
_CERTS_FALLBACK_TTL = 3600

# Clock skew allowed on exp/iat. Phones with a drifting clock are common.
_LEEWAY_SECONDS = 60

_jwt = JsonWebToken(["RS256"])


class GoogleIdentityError(Exception):
    """The token is not a usable Google identity.

    Never rendered to a client verbatim — the message is for the log. What the
    caller shows is "sign-in failed", because the difference between a forged
    token and an expired one is not the user's business and telling them apart
    helps only an attacker.
    """


@dataclass(frozen=True)
class GoogleIdentity:
    """The claims we act on, from either flow."""

    subject: str
    email: str
    email_verified: bool
    name: str | None = None
    picture: str | None = None
    nonce: str | None = None


def accepted_audiences(settings: Settings) -> tuple[str, ...]:
    """Client ids whose ID tokens this deployment accepts.

    `GOOGLE_CLIENT_ID` is in here because Android's Credential Manager is asked
    for a token for the *web* client id (`serverClientId`) — the Android client
    id never appears in the `aud` claim. `GOOGLE_MOBILE_CLIENT_IDS` exists for
    the other direction: a self-hoster running the published app against their
    own backend has to accept the app's client id, which is not theirs.
    """
    ids = [settings.GOOGLE_CLIENT_ID, *settings.GOOGLE_MOBILE_CLIENT_IDS]
    return tuple(dict.fromkeys(i.strip() for i in ids if i.strip()))


# --- JWKS cache ---------------------------------------------------------------

_certs_cache: dict[str, Any] | None = None
_certs_expires_at: float = 0.0


def reset_certs_cache() -> None:
    """Drop the cached key set. For tests."""
    global _certs_cache, _certs_expires_at
    _certs_cache = None
    _certs_expires_at = 0.0


def _cache_ttl(response: httpx.Response) -> int:
    cache_control = response.headers.get("cache-control", "")
    for part in cache_control.split(","):
        part = part.strip()
        if part.startswith("max-age="):
            try:
                return max(int(part.removeprefix("max-age=")), 0)
            except ValueError:
                break
    return _CERTS_FALLBACK_TTL


async def _fetch_certs() -> dict[str, Any]:
    global _certs_cache, _certs_expires_at
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(GOOGLE_CERTS_URL)
    if response.status_code != 200:
        raise GoogleIdentityError(f"Google key set unavailable: HTTP {response.status_code}")
    certs: dict[str, Any] = response.json()
    _certs_cache = certs
    _certs_expires_at = time.time() + _cache_ttl(response)
    return certs


async def _certs(*, force_refresh: bool = False) -> dict[str, Any]:
    if not force_refresh and _certs_cache is not None and time.time() < _certs_expires_at:
        return _certs_cache
    return await _fetch_certs()


# --- Verification -------------------------------------------------------------


async def verify_id_token(
    raw_token: str,
    settings: Settings,
    *,
    expected_nonce: str | None = None,
) -> GoogleIdentity:
    """Verify a Google-issued ID token and return the identity it asserts.

    Raises [GoogleIdentityError] for anything that makes the token unusable:
    bad signature, wrong issuer, an audience this deployment does not accept,
    expiry, or a nonce that does not match the one we handed out.
    """
    audiences = accepted_audiences(settings)
    if not audiences:
        raise GoogleIdentityError("Google sign-in is not configured: GOOGLE_CLIENT_ID is empty")

    claims_options = {
        "iss": {"essential": True, "values": list(GOOGLE_ISSUERS)},
        "aud": {"essential": True, "values": list(audiences)},
        "sub": {"essential": True},
        "exp": {"essential": True},
    }

    claims = None
    for force_refresh in (False, True):
        certs = await _certs(force_refresh=force_refresh)
        try:
            claims = _jwt.decode(
                raw_token,
                key=JsonWebKey.import_key_set(certs),
                claims_options=claims_options,
            )
            break
        except ValueError as exc:
            # authlib raises this when the token's `kid` is absent from the key
            # set — the signature of a rotation we have not fetched yet. Worth
            # exactly one refetch; a forged kid then fails for good.
            if force_refresh:
                raise GoogleIdentityError(f"Unknown signing key: {exc}") from exc
        except JoseError as exc:
            raise GoogleIdentityError(f"Token rejected: {exc}") from exc

    if claims is None:  # pragma: no cover - the loop either breaks or raises
        raise GoogleIdentityError("Token could not be decoded")

    try:
        claims.validate(leeway=_LEEWAY_SECONDS)
    except JoseError as exc:
        raise GoogleIdentityError(f"Claims rejected: {exc}") from exc

    email = claims.get("email")
    if not email:
        raise GoogleIdentityError("Token carries no email")

    token_nonce = claims.get("nonce")
    if expected_nonce is not None and token_nonce != expected_nonce:
        raise GoogleIdentityError("Nonce mismatch")

    return GoogleIdentity(
        subject=str(claims["sub"]),
        email=str(email),
        # Google sends this as a bool, older tokens as the string "true".
        email_verified=claims.get("email_verified") in (True, "true"),
        name=claims.get("name"),
        picture=claims.get("picture"),
        nonce=token_nonce,
    )


# --- Account resolution -------------------------------------------------------


async def resolve_google_account(
    session: AsyncSession,
    identity: GoogleIdentity,
) -> tuple[User, bool]:
    """Find, link or create the account behind a Google identity.

    Returns the user and whether it was created just now.

    Linking to an existing local account by email address is only done when
    Google attests the address is verified — otherwise anyone able to set an
    unverified alias on a Google account could take over the unefy account
    with that address.
    """
    stmt = select(User).where(User.google_id == identity.subject)
    user = (await session.execute(stmt)).scalar_one_or_none()

    if user is not None:
        if identity.name and user.name != identity.name:
            user.name = identity.name
        if identity.picture:
            user.image = identity.picture
        await session.flush()
        return user, False

    if not identity.email_verified:
        logger.warning("oauth_unverified_email", google_sub=identity.subject)
        raise GoogleIdentityError("Google has not verified this address")

    stmt = select(User).where(User.email == identity.email)
    user = (await session.execute(stmt)).scalar_one_or_none()

    if user is None:
        user = User(
            email=identity.email,
            name=identity.name or identity.email.split("@")[0],
            image=identity.picture,
            email_verified=True,
            google_id=identity.subject,
        )
        session.add(user)
        await session.flush()
        logger.info("user_created", user_id=str(user.id), method="google")
        return user, True

    user.google_id = identity.subject
    if identity.picture and not user.image:
        user.image = identity.picture
    if not user.email_verified:
        user.email_verified = True
    await session.flush()
    logger.info("account_linked", user_id=str(user.id), method="google")
    return user, False
