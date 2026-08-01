import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database import get_db_session
from app.dependencies import AuthContext, require_role
from app.schemas.catalog import (
    ClubDisciplineCreate,
    ClubDisciplineResponse,
    ClubDisciplineUpdate,
    DisciplineImportRequest,
)
from app.services.catalog import CatalogService

router = APIRouter()


@router.get("")
async def list_club_disciplines(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    include_inactive: bool = Query(default=False),
) -> dict[str, Any]:
    """List club disciplines."""
    service = CatalogService(session, auth.tenant)
    disciplines = await service.disciplines.get_all(include_inactive=include_inactive)
    return {
        "data": [
            ClubDisciplineResponse.model_validate(d).model_dump(mode="json") for d in disciplines
        ]
    }


@router.post("", status_code=201)
async def create_club_discipline(
    data: ClubDisciplineCreate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Create a club discipline."""
    service = CatalogService(session, auth.tenant)
    discipline = await service.create_discipline(data, created_by=auth.user_id)
    return {"data": ClubDisciplineResponse.model_validate(discipline).model_dump(mode="json")}


@router.post("/import", status_code=201)
async def import_club_disciplines(
    data: DisciplineImportRequest,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Import disciplines from the global catalog, skipping existing names."""
    service = CatalogService(session, auth.tenant)
    created = await service.import_from_catalog(data.discipline_ids, created_by=auth.user_id)
    return {
        "data": [ClubDisciplineResponse.model_validate(d).model_dump(mode="json") for d in created]
    }


@router.patch("/{discipline_id}")
async def update_club_discipline(
    discipline_id: uuid.UUID,
    data: ClubDisciplineUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Update a club discipline."""
    service = CatalogService(session, auth.tenant)
    discipline = await service.update_discipline(discipline_id, data, updated_by=auth.user_id)
    if discipline is None:
        raise NotFoundError("Discipline not found")
    return {"data": ClubDisciplineResponse.model_validate(discipline).model_dump(mode="json")}


@router.delete("/{discipline_id}", status_code=204)
async def delete_club_discipline(
    discipline_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> None:
    """Soft-delete a club discipline."""
    service = CatalogService(session, auth.tenant)
    deleted = await service.disciplines.soft_delete(discipline_id)
    if not deleted:
        raise NotFoundError("Discipline not found")
