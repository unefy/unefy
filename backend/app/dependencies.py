import hmac
import uuid
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ForbiddenError
from app.database import get_db_session
from app.models.user import TenantMembership
from app.redis import get_redis

__all__ = ["get_current_user", "get_db_session", "get_redis"]

COOKIE_NAME = "unefy_session"


@dataclass(frozen=True)
class AuthContext:
    """Resolved user identity with tenant context."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    role: str | None = None


async def _resolve_auth(
    request: Request,
    session: AsyncSession,
) -> AuthContext | None:
    """Low-level auth resolution. Returns None if not authenticated.

    Used by endpoints that need to handle unauthenticated or
    partially-authenticated (onboarding) users gracefully.
    """
    # Session cookie
    session_token = request.cookies.get(COOKIE_NAME)
    if session_token:
        from app.api.v1.auth import get_session_data

        data = await get_session_data(session_token)
        if data:
            user_id, tenant_id, role = data
            return AuthContext(user_id=user_id, tenant_id=tenant_id, role=role)

    # Internal trust headers (BFF)
    x_user_id = request.headers.get("x-user-id")
    x_tenant_id = request.headers.get("x-tenant-id")
    x_secret = request.headers.get("x-internal-secret")

    if x_user_id and x_tenant_id and x_secret:
        settings = get_settings()
        if not hmac.compare_digest(x_secret, settings.INTERNAL_API_SECRET):
            return None

        user_id = uuid.UUID(x_user_id)
        tenant_id = uuid.UUID(x_tenant_id)

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


def require_role(*allowed_roles: str):
    """Dependency that checks if the user has one of the allowed roles."""

    async def check_role(
        auth: AuthContext = Depends(get_current_user),  # noqa: B008
    ) -> AuthContext:
        if auth.role not in allowed_roles:
            allowed = ", ".join(allowed_roles)
            raise ForbiddenError(f"Role '{auth.role}' not allowed. Required: {allowed}")
        return auth

    return check_role
