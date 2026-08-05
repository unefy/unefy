"""Mobile auth endpoints — JWT access + refresh tokens.

Scope:
- POST /magic-link/request  (mails a one-time login code)
- POST /magic-link/verify   (code → JWT pair; creates the user on first login)
- POST /dev/login           (DEBUG only, for local development)
- POST /refresh             (rotates refresh token)
- POST /switch-tenant       (re-issues the pair for another club)
- POST /logout              (revokes refresh token)

Google OAuth and passkey flows are added in later phases.
"""

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.core.jwt import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.rate_limit import RateLimit
from app.database import get_db_session
from app.dependencies import AuthContext, get_current_user
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User
from app.redis import get_redis
from app.services.magic_link import consume_otp, issue_otp, resolve_user, send_login_code

logger = structlog.get_logger()
router = APIRouter()


# --- Refresh-token store (Redis) ----------------------------------------------

_REFRESH_KEY_PREFIX = "refresh:"


async def _store_refresh_jti(jti: str, user_id: uuid.UUID) -> None:
    redis = get_redis()
    ttl = get_settings().JWT_REFRESH_TTL_SECONDS
    await redis.set(f"{_REFRESH_KEY_PREFIX}{jti}", str(user_id), ex=ttl)


async def _delete_refresh_jti(jti: str) -> None:
    redis = get_redis()
    await redis.delete(f"{_REFRESH_KEY_PREFIX}{jti}")


async def _refresh_jti_owner(jti: str) -> uuid.UUID | None:
    redis = get_redis()
    raw = await redis.get(f"{_REFRESH_KEY_PREFIX}{jti}")
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except ValueError:
        return None


# --- Response building --------------------------------------------------------


class _NoActiveMembershipError(AppError):
    def __init__(self, message: str = "No active membership") -> None:
        super().__init__(status_code=412, code="PRECONDITION_FAILED", message=message)


async def _issue_token_pair(
    user: User,
    tenant: Tenant,
    membership: TenantMembership,
) -> dict[str, Any]:
    access_token, _ = create_access_token(
        user_id=user.id,
        tenant_id=tenant.id,
        role=membership.role,
    )
    refresh_token, refresh_jti = create_refresh_token(user_id=user.id)
    await _store_refresh_jti(refresh_jti, user.id)

    settings = get_settings()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "access_expires_in": settings.JWT_ACCESS_TTL_SECONDS,
        "refresh_expires_in": settings.JWT_REFRESH_TTL_SECONDS,
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "image": user.image,
            "locale": user.locale,
        },
        "tenant": {
            "id": str(tenant.id),
            "name": tenant.name,
            "slug": tenant.slug,
            "short_name": tenant.short_name,
        },
        "role": membership.role,
    }


async def _load_first_active_tenant(
    session: AsyncSession, user_id: uuid.UUID
) -> tuple[Tenant, TenantMembership]:
    stmt = (
        select(TenantMembership, Tenant)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .where(TenantMembership.user_id == user_id)
        .where(TenantMembership.is_active.is_(True))
        .order_by(TenantMembership.joined_at.asc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        raise _NoActiveMembershipError()
    membership, tenant = row
    return tenant, membership


async def _load_active_tenant(
    session: AsyncSession, user_id: uuid.UUID, tenant_id: uuid.UUID
) -> tuple[Tenant, TenantMembership] | None:
    """The user's active membership in exactly this tenant, or None."""
    stmt = (
        select(TenantMembership, Tenant)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .where(TenantMembership.user_id == user_id)
        .where(TenantMembership.tenant_id == tenant_id)
        .where(TenantMembership.is_active.is_(True))
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        return None
    membership, tenant = row
    return tenant, membership


# --- Endpoints ----------------------------------------------------------------


class MagicLinkRequestBody(BaseModel):
    email: EmailStr


@router.post(
    "/magic-link/request",
    dependencies=[
        # A mail sender behind an open endpoint; keep it slow.
        Depends(RateLimit(limit=5, window=300, scope="mobile-magic-request")),
    ],
)
async def magic_link_request(
    data: MagicLinkRequestBody,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Mail a one-time login code.

    Always 200, whether the account exists or not — the same
    anti-enumeration stance as the web endpoint. The user is only created on
    successful *verification*, so requesting codes for strangers' addresses
    leaves no trace.
    """
    code = await issue_otp(data.email, settings)
    await send_login_code(data.email, code, settings)
    return {"data": {"sent": True}}


class MagicLinkVerifyBody(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


@router.post(
    "/magic-link/verify",
    dependencies=[
        # The service already caps guesses per code; this caps callers that
        # rotate addresses.
        Depends(RateLimit(limit=15, window=300, scope="mobile-magic-verify")),
    ],
)
async def magic_link_verify(
    data: MagicLinkVerifyBody,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Redeem a login code for a JWT pair, creating the user on first login.

    412 when the fresh account belongs to no club yet — the app shows "ask
    your club for an invitation" instead of a token it could do nothing with.
    """
    if not await consume_otp(data.email, data.code, settings):
        raise ForbiddenError("Invalid or expired code")

    user = await resolve_user(session, data.email)
    tenant, membership = await _load_first_active_tenant(session, user.id)
    payload = await _issue_token_pair(user, tenant, membership)

    logger.info("mobile_magic_login", user_id=str(user.id), tenant_id=str(tenant.id))
    return {"data": payload}


class DevLoginRequest(BaseModel):
    email: EmailStr


@router.post(
    "/dev/login",
    dependencies=[Depends(RateLimit(limit=10, window=60, scope="mobile-dev-login"))],
)
async def dev_login(
    data: DevLoginRequest,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Dev-only mobile login. Returns JWT pair for an existing user.

    Only enabled when `DEBUG=true`. Looks up the user by email, picks the
    first active tenant membership, and issues an access+refresh token pair.
    The user must already exist — this is a shortcut for local iOS testing,
    not a user-creation endpoint.
    """
    if not settings.DEBUG:
        raise NotFoundError()

    stmt = select(User).where(User.email == data.email)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError("User not found")

    tenant, membership = await _load_first_active_tenant(session, user.id)
    payload = await _issue_token_pair(user, tenant, membership)

    logger.info("mobile_dev_login", user_id=str(user.id), tenant_id=str(tenant.id))
    return {"data": payload}


class RefreshRequest(BaseModel):
    refresh_token: str
    # The tenant the app is currently signed into. Without it a refresh always
    # re-pinned to the *first* membership, silently undoing a tenant switch on
    # the next rotation. Optional for old clients; a stale or revoked value
    # falls back to the first active membership rather than bricking refresh.
    tenant_id: uuid.UUID | None = None


@router.post(
    "/refresh",
    dependencies=[Depends(RateLimit(limit=60, window=60, scope="mobile-refresh"))],
)
async def refresh(
    data: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Rotate refresh token and issue a new access+refresh pair."""
    try:
        claims = decode_token(data.refresh_token)
    except InvalidTokenError as exc:
        raise ForbiddenError("Invalid refresh token") from exc

    if claims.get("type") != "refresh":
        raise ForbiddenError("Wrong token type")

    jti = str(claims.get("jti") or "")
    sub = str(claims.get("sub") or "")
    if not jti or not sub:
        raise ForbiddenError("Malformed refresh token")

    owner = await _refresh_jti_owner(jti)
    if owner is None or str(owner) != sub:
        raise ForbiddenError("Refresh token revoked or unknown")

    try:
        user_id = uuid.UUID(sub)
    except ValueError as exc:
        raise ForbiddenError("Malformed refresh token") from exc

    # Rotate: invalidate old jti immediately to prevent reuse during load
    await _delete_refresh_jti(jti)

    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise ForbiddenError("User not found")

    preferred = None
    if data.tenant_id is not None:
        preferred = await _load_active_tenant(session, user.id, data.tenant_id)
    tenant, membership = preferred or await _load_first_active_tenant(session, user.id)
    payload = await _issue_token_pair(user, tenant, membership)

    logger.info("mobile_refresh", user_id=str(user.id), old_jti=jti)
    return {"data": payload}


class SwitchTenantRequest(BaseModel):
    tenant_id: uuid.UUID


@router.post(
    "/switch-tenant",
    dependencies=[Depends(RateLimit(limit=20, window=60, scope="mobile-switch-tenant"))],
)
async def switch_tenant(
    data: SwitchTenantRequest,
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Re-issue the token pair for another of the caller's clubs.

    The mobile counterpart of the web's cookie-rotating `/auth/switch-tenant`:
    a mobile JWT is tenant-scoped, so switching *is* a re-issue. Membership is
    checked here and nowhere weaker — the token that comes back carries the
    role the target club actually granted, not the one the caller had.
    """
    stmt = select(User).where(User.id == auth.user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise ForbiddenError("User not found")

    loaded = await _load_active_tenant(session, user.id, data.tenant_id)
    if loaded is None:
        # Indistinguishable from a club that does not exist: whether the
        # caller was never a member or was deactivated is not theirs to probe.
        raise NotFoundError("Club not found")
    tenant, membership = loaded

    payload = await _issue_token_pair(user, tenant, membership)
    logger.info("mobile_switch_tenant", user_id=str(user.id), tenant_id=str(tenant.id))
    return {"data": payload}


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post(
    "/logout",
    dependencies=[Depends(RateLimit(limit=20, window=60, scope="mobile-logout"))],
)
async def logout(data: LogoutRequest) -> dict[str, Any]:
    """Revoke a refresh token. Idempotent — unknown jtis return success."""
    try:
        claims = decode_token(data.refresh_token)
    except InvalidTokenError:
        # Token already useless; treat as success to keep logout idempotent
        # even when the token is expired or tampered with.
        return {"data": {"message": "Logged out"}}

    if claims.get("type") == "refresh":
        jti = str(claims.get("jti") or "")
        if jti:
            await _delete_refresh_jti(jti)

    return {"data": {"message": "Logged out"}}
