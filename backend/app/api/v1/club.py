import json

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database import get_db_session
from app.dependencies import AuthContext, get_current_user, require_role
from app.models.tenant import Tenant
from app.models.user import TenantMembership
from app.redis import get_redis
from app.schemas.club import ClubResponse, ClubUpdate

logger = structlog.get_logger()

router = APIRouter()


@router.get("")
async def get_club(
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict:
    """Get the current club's details."""
    stmt = select(Tenant).where(Tenant.id == auth.tenant_id)
    result = await session.execute(stmt)
    tenant = result.scalar_one_or_none()

    if tenant is None:
        raise NotFoundError("Club not found")

    return {"data": ClubResponse.model_validate(tenant).model_dump()}


@router.patch("")
async def update_club(
    data: ClubUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict:
    """Update the current club. Requires owner or admin role."""
    stmt = select(Tenant).where(Tenant.id == auth.tenant_id)
    result = await session.execute(stmt)
    tenant = result.scalar_one_or_none()

    if tenant is None:
        raise NotFoundError("Club not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(tenant, field, value)

    await session.flush()
    await session.refresh(tenant)

    return {"data": ClubResponse.model_validate(tenant).model_dump()}


COOKIE_NAME = "unefy_session"
SESSION_TTL = 60 * 60 * 24 * 7


@router.delete("")
async def delete_club(
    request: Request,
    auth: AuthContext = Depends(require_role("owner")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict:
    """Delete the current club. Only owner can delete. User account is preserved."""
    # Delete all memberships for this tenant
    await session.execute(
        delete(TenantMembership).where(TenantMembership.tenant_id == auth.tenant_id)
    )

    # Delete the tenant
    stmt = select(Tenant).where(Tenant.id == auth.tenant_id)
    result = await session.execute(stmt)
    tenant = result.scalar_one_or_none()

    if tenant is None:
        raise NotFoundError("Club not found")

    await session.delete(tenant)
    await session.flush()

    # Update session to remove tenant context (user goes to onboarding)
    session_token = request.cookies.get(COOKIE_NAME)
    if session_token:
        redis = get_redis()
        session_data = json.dumps(
            {
                "user_id": str(auth.user_id),
                "tenant_id": None,
                "role": None,
            }
        )
        await redis.set(f"session:{session_token}", session_data, ex=SESSION_TTL)

    logger.info("club_deleted", tenant_id=str(auth.tenant_id), user_id=str(auth.user_id))

    return {"data": {"message": "Club deleted"}}
