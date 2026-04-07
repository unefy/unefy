"""JWT utilities for mobile auth (access + refresh tokens).

Tokens are signed with HS256 using `settings.JWT_SECRET`. Claims follow RFC 7519:

- Access token: `sub` (user_id), `tid` (tenant_id), `role`, `type="access"`,
  `jti`, `iat`, `exp`.
- Refresh token: `sub` (user_id), `type="refresh"`, `jti`, `iat`, `exp`.

Refresh tokens are tracked in Redis (`refresh:{jti} -> user_id`) so we can
revoke them on logout and rotate them on refresh.
"""

import secrets
import time
import uuid
from typing import Any

from authlib.jose import JoseError, jwt  # type: ignore[import-untyped]

from app.config import get_settings

_ALG = "HS256"


class InvalidTokenError(Exception):
    """Raised when a JWT cannot be decoded/verified."""


def _now() -> int:
    return int(time.time())


def _encode(payload: dict[str, Any]) -> str:
    secret = get_settings().JWT_SECRET
    token = jwt.encode({"alg": _ALG}, payload, secret)
    # authlib returns bytes
    return token.decode("ascii") if isinstance(token, bytes) else token


def create_access_token(
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
) -> tuple[str, str]:
    """Return (token, jti)."""
    settings = get_settings()
    now = _now()
    jti = secrets.token_urlsafe(16)
    payload = {
        "sub": str(user_id),
        "tid": str(tenant_id),
        "role": role,
        "type": "access",
        "jti": jti,
        "iat": now,
        "exp": now + settings.JWT_ACCESS_TTL_SECONDS,
    }
    return _encode(payload), jti


def create_refresh_token(*, user_id: uuid.UUID) -> tuple[str, str]:
    """Return (token, jti)."""
    settings = get_settings()
    now = _now()
    jti = secrets.token_urlsafe(16)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "exp": now + settings.JWT_REFRESH_TTL_SECONDS,
    }
    return _encode(payload), jti


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises InvalidTokenError on any failure."""
    secret = get_settings().JWT_SECRET
    try:
        claims = jwt.decode(token, secret)
        claims.validate(now=_now(), leeway=0)
    except JoseError as exc:
        raise InvalidTokenError(str(exc)) from exc
    except Exception as exc:  # defensive — malformed tokens
        raise InvalidTokenError(str(exc)) from exc
    return dict(claims)
