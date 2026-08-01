import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database import get_db_session
from app.dependencies import AuthContext, require_role
from app.schemas.catalog import (
    MeasurementUnitCreate,
    MeasurementUnitResponse,
    MeasurementUnitUpdate,
)
from app.services.catalog import CatalogService

router = APIRouter()


@router.get("")
async def list_units(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    include_inactive: bool = Query(default=False),
) -> dict[str, Any]:
    """List measurement units."""
    service = CatalogService(session, auth.tenant)
    units = await service.units.get_all(include_inactive=include_inactive)
    return {
        "data": [MeasurementUnitResponse.model_validate(u).model_dump(mode="json") for u in units]
    }


@router.post("", status_code=201)
async def create_unit(
    data: MeasurementUnitCreate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Create a measurement unit."""
    service = CatalogService(session, auth.tenant)
    unit = await service.create_unit(data, created_by=auth.user_id)
    return {"data": MeasurementUnitResponse.model_validate(unit).model_dump(mode="json")}


@router.patch("/{unit_id}")
async def update_unit(
    unit_id: uuid.UUID,
    data: MeasurementUnitUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Update a measurement unit."""
    service = CatalogService(session, auth.tenant)
    unit = await service.update_unit(unit_id, data, updated_by=auth.user_id)
    if unit is None:
        raise NotFoundError("Unit not found")
    return {"data": MeasurementUnitResponse.model_validate(unit).model_dump(mode="json")}


@router.delete("/{unit_id}", status_code=204)
async def delete_unit(
    unit_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> None:
    """Soft-delete a measurement unit."""
    service = CatalogService(session, auth.tenant)
    deleted = await service.units.soft_delete(unit_id)
    if not deleted:
        raise NotFoundError("Unit not found")
