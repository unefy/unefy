from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database import get_db_session
from app.dependencies import AuthContext, get_current_user, require_role
from app.models.tenant import Tenant
from app.schemas.club import ClubResponse, ClubUpdate

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
