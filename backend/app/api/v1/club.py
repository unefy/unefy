import json
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database import get_db_session
from app.dependencies import AuthContext, get_current_user, require_role
from app.models.sport import Sport
from app.models.tenant import Tenant
from app.models.tenant_sport import TenantSport
from app.models.user import TenantMembership
from app.redis import get_redis
from app.schemas.club import ClubResponse, ClubSportsUpdate, ClubUpdate

logger = structlog.get_logger()

router = APIRouter()


async def _sports_and_modules(
    session: AsyncSession, tenant_id: uuid.UUID
) -> tuple[list[dict[str, Any]], list[str]]:
    """The club's sports and the modules they activate.

    Modules are the union over the club's sports: a Turnverein with a shooting
    section gets the shooting module without that being a special case. The
    mapping sport -> modules lives in `sports.modules` and is validated against
    the code registry, so this can only ever return implemented modules.
    """
    rows = await session.execute(
        select(Sport, TenantSport.is_primary)
        .join(TenantSport, TenantSport.sport_id == Sport.id)
        .where(TenantSport.tenant_id == tenant_id)
        .order_by(TenantSport.is_primary.desc(), Sport.sort_order)
    )
    pairs = rows.all()
    sports = [
        {
            "id": str(sport.id),
            "key": sport.key,
            "name": sport.name,
            "icon": sport.icon,
            "is_primary": is_primary,
        }
        for sport, is_primary in pairs
    ]
    modules = sorted({module for sport, _ in pairs for module in sport.modules})
    return sports, modules


@router.get("")
async def get_club(
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Get the current club's details."""
    stmt = select(Tenant).where(Tenant.id == auth.tenant_id)
    result = await session.execute(stmt)
    tenant = result.scalar_one_or_none()

    if tenant is None:
        raise NotFoundError("Club not found")

    sports, modules = await _sports_and_modules(session, auth.tenant)
    return {
        "data": ClubResponse.model_validate(tenant).model_dump()
        | {"sports": sports, "modules": modules}
    }


@router.patch("")
async def update_club(
    data: ClubUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
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
) -> dict[str, Any]:
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


@router.put("/sports")
async def set_club_sports(
    data: ClubSportsUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Replace the club's sports.

    A full replace rather than add/remove endpoints: the set is small, the UI
    edits it as a whole, and a replace has no partial-failure state to reason
    about. Unknown sport ids are rejected before anything is written.
    """
    known = await session.execute(select(Sport.id).where(Sport.id.in_(data.sport_ids)))
    known_ids = {row[0] for row in known}
    missing = [str(sid) for sid in data.sport_ids if sid not in known_ids]
    if missing:
        raise NotFoundError(f"Unknown sport ids: {', '.join(missing)}")

    await session.execute(delete(TenantSport).where(TenantSport.tenant_id == auth.tenant))
    for sport_id in data.sport_ids:
        session.add(
            TenantSport(
                tenant_id=auth.tenant,
                sport_id=sport_id,
                is_primary=sport_id == data.primary_sport_id,
            )
        )
    await session.flush()

    sports, modules = await _sports_and_modules(session, auth.tenant)
    return {"data": {"sports": sports, "modules": modules}}
