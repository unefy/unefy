import hmac
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

import structlog
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import AppError, ForbiddenError
from app.core.jwt import InvalidTokenError, decode_token
from app.database import get_db_session
from app.models.user import TenantMembership
from app.redis import get_redis

__all__ = ["get_current_user", "get_db_session", "get_redis"]

logger = structlog.get_logger()

COOKIE_NAME = "unefy_session"

# Brute-force protection for the BFF shared secret: after this many failed
# secret validations per IP within the window, further attempts are rejected
# without comparison.
_BFF_FAIL_LIMIT = 10
_BFF_FAIL_WINDOW = 300


async def _bff_secret_failures(ip: str) -> int:
    redis = get_redis()
    raw = await redis.get(f"bff-secret-fail:{ip}")
    return int(raw) if raw else 0


async def _record_bff_secret_failure(ip: str) -> None:
    redis = get_redis()
    key = f"bff-secret-fail:{ip}"
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, _BFF_FAIL_WINDOW)
    logger.warning("bff_secret_invalid", ip=ip, failures=current)


@dataclass(frozen=True)
class AuthContext:
    """Resolved user identity with tenant context."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    role: str | None = None

    # Set only while a platform admin is impersonating. `user_id` remains the
    # impersonated user, so authorization keeps evaluating the effective
    # identity — this field exists for audit attribution, never for access.
    impersonator_id: uuid.UUID | None = None

    @property
    def is_impersonated(self) -> bool:
        return self.impersonator_id is not None

    @property
    def tenant(self) -> uuid.UUID:
        """The tenant, as a value that is actually there.

        `get_current_user` already refuses a session without one, so every
        endpoint behind it has a tenant — but `tenant_id` stays optional
        because onboarding and the platform-admin area legitimately have none.
        This property states the guarantee once, instead of leaving every
        repository call site to shrug at `UUID | None`.
        """
        if self.tenant_id is None:
            raise ForbiddenError("No tenant context. Complete onboarding first.")
        return self.tenant_id


class InvalidBearerTokenError(AppError):
    def __init__(self, message: str = "Invalid or expired token") -> None:
        super().__init__(status_code=401, code="INVALID_TOKEN", message=message)


async def _resolve_bearer(
    request: Request,
    session: AsyncSession,
) -> AuthContext | None:
    """Resolve a mobile Bearer JWT. Returns None if no bearer header present.

    Raises InvalidBearerTokenError if a bearer header is present but invalid —
    the caller explicitly asserted an identity, so we must not silently fall
    through to other auth mechanisms.
    """
    header = request.headers.get("authorization")
    if not header or not header.lower().startswith("bearer "):
        return None

    token = header.split(" ", 1)[1].strip()
    if not token:
        return None

    try:
        claims = decode_token(token)
    except InvalidTokenError as exc:
        raise InvalidBearerTokenError() from exc

    if claims.get("type") != "access":
        raise InvalidBearerTokenError("Wrong token type")

    try:
        user_id = uuid.UUID(str(claims["sub"]))
        tenant_id = uuid.UUID(str(claims["tid"]))
    except (KeyError, ValueError) as exc:
        raise InvalidBearerTokenError("Malformed token claims") from exc

    # Verify membership is still active — so revoked roles are rejected
    # even with a valid (not-yet-expired) token.
    stmt = (
        select(TenantMembership)
        .where(TenantMembership.user_id == user_id)
        .where(TenantMembership.tenant_id == tenant_id)
        .where(TenantMembership.is_active.is_(True))
    )
    result = await session.execute(stmt)
    membership = result.scalar_one_or_none()
    if membership is None:
        raise InvalidBearerTokenError("Membership no longer active")

    return AuthContext(user_id=user_id, tenant_id=tenant_id, role=membership.role)


async def _resolve_auth(
    request: Request,
    session: AsyncSession,
) -> AuthContext | None:
    """Low-level auth resolution. Returns None if not authenticated.

    Used by endpoints that need to handle unauthenticated or
    partially-authenticated (onboarding) users gracefully.
    """
    # Mobile Bearer JWT (checked first — explicit client assertion)
    bearer = await _resolve_bearer(request, session)
    if bearer is not None:
        return bearer

    # Session cookie
    session_token = request.cookies.get(COOKIE_NAME)
    if session_token:
        from app.api.v1.auth import get_session_data

        data = await get_session_data(session_token)
        if data:
            return AuthContext(
                user_id=data.user_id,
                tenant_id=data.tenant_id,
                role=data.role,
                impersonator_id=data.impersonator_id,
            )

    # Internal trust headers (BFF)
    x_user_id = request.headers.get("x-user-id")
    x_tenant_id = request.headers.get("x-tenant-id")
    x_secret = request.headers.get("x-internal-secret")

    if x_user_id and x_tenant_id and x_secret:
        from app.core.rate_limit import _client_ip

        ip = _client_ip(request)
        if await _bff_secret_failures(ip) >= _BFF_FAIL_LIMIT:
            return None

        settings = get_settings()
        if not hmac.compare_digest(x_secret, settings.INTERNAL_API_SECRET):
            await _record_bff_secret_failure(ip)
            return None

        try:
            user_id = uuid.UUID(x_user_id)
            tenant_id = uuid.UUID(x_tenant_id)
        except ValueError:
            return None

        stmt = (
            select(TenantMembership)
            .where(TenantMembership.user_id == user_id)
            .where(TenantMembership.tenant_id == tenant_id)
            .where(TenantMembership.is_active.is_(True))
        )
        result = await session.execute(stmt)
        membership = result.scalar_one_or_none()

        if membership:
            return AuthContext(user_id=user_id, tenant_id=tenant_id, role=membership.role)

    return None


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> AuthContext:
    """Resolve authenticated user. Raises 403 if not authenticated or no tenant."""
    auth = await _resolve_auth(request, session)

    if auth is None:
        raise ForbiddenError("No valid authentication provided")

    if auth.tenant_id is None:
        raise ForbiddenError("No tenant context. Complete onboarding first.")

    return auth


async def get_authenticated_user(
    request: Request,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> AuthContext:
    """Resolve an authenticated user without requiring tenant context.

    Used by endpoints that operate outside any club — onboarding and the
    platform admin area. Prefer `get_current_user` everywhere else: it
    guarantees a tenant, which tenant-scoped repositories depend on.
    """
    auth = await _resolve_auth(request, session)
    if auth is None:
        raise ForbiddenError("No valid authentication provided")
    return auth


async def require_platform_admin(
    request: Request,
    auth: AuthContext = Depends(get_authenticated_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> AuthContext:
    """Gate for `/api/v1/admin/…` — the platform operator, above all tenants.

    This deliberately bypasses tenant isolation, so it is the one place where a
    mistake leaks every club's data. Three rules hold it together:

    1. The flag is read from the database on every request, not from the
       session — revoking it takes effect immediately instead of at session
       expiry.
    2. An impersonated session is rejected outright. `user_id` is already the
       impersonated (non-admin) user, so the flag check would fail anyway; the
       explicit check makes the intent non-accidental and survives refactors.
    3. Failures are logged with the client IP, because probing this endpoint is
       a meaningful security signal.
    """
    if auth.is_impersonated:
        from app.core.rate_limit import _client_ip

        logger.warning(
            "platform_admin_denied_impersonated",
            user_id=str(auth.user_id),
            impersonator_id=str(auth.impersonator_id),
            ip=_client_ip(request),
        )
        raise ForbiddenError("Platform admin actions are unavailable while impersonating")

    from app.models.user import User

    result = await session.execute(select(User.is_superuser).where(User.id == auth.user_id))
    is_superuser = result.scalar_one_or_none()

    if not is_superuser:
        from app.core.rate_limit import _client_ip

        logger.warning(
            "platform_admin_denied",
            user_id=str(auth.user_id),
            ip=_client_ip(request),
        )
        raise ForbiddenError("Platform administrator access required")

    return auth


def require_role(*allowed_roles: str) -> Callable[..., Coroutine[Any, Any, AuthContext]]:
    """Dependency that checks if the user has one of the allowed roles."""

    async def check_role(
        auth: AuthContext = Depends(get_current_user),  # noqa: B008
    ) -> AuthContext:
        if auth.role not in allowed_roles:
            allowed = ", ".join(allowed_roles)
            raise ForbiddenError(f"Role '{auth.role}' not allowed. Required: {allowed}")
        return auth

    return check_role
