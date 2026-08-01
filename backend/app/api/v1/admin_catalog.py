import math
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.modules import AVAILABLE_MODULES
from app.database import get_db_session
from app.dependencies import AuthContext, require_platform_admin
from app.schemas.catalog_admin import (
    CatalogDisciplineCreate,
    CatalogDisciplineResponse,
    CatalogDisciplineUpdate,
    CatalogUnitCreate,
    CatalogUnitResponse,
    CatalogUnitUpdate,
    SportCreate,
    SportResponse,
    SportUpdate,
)
from app.services.admin_catalog import AdminCatalogService

router = APIRouter()


def _service(session: AsyncSession) -> AdminCatalogService:
    return AdminCatalogService(session)


# --- Modules ---


@router.get("/modules")
async def list_modules(
    _auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
) -> dict[str, Any]:
    """Sport modules that exist in code and can be assigned to a sport."""
    return {"data": [{"key": key, "label": label} for key, label in AVAILABLE_MODULES.items()]}


# --- Sports ---


@router.get("/sports")
async def list_sports(
    _auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    include_inactive: bool = Query(default=True),
) -> dict[str, Any]:
    return {"data": await _service(session).list_sports(include_inactive=include_inactive)}


@router.post("/sports", status_code=201)
async def create_sport(
    data: SportCreate,
    request: Request,
    auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    sport = await _service(session).create_sport(auth, data, request)
    await session.commit()
    return {"data": SportResponse.model_validate(sport)}


@router.patch("/sports/{sport_id}")
async def update_sport(
    sport_id: uuid.UUID,
    data: SportUpdate,
    request: Request,
    auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    sport = await _service(session).update_sport(auth, sport_id, data, request)
    await session.commit()
    return {"data": SportResponse.model_validate(sport)}


@router.delete("/sports/{sport_id}", status_code=204)
async def delete_sport(
    sport_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> Response:
    await _service(session).delete_sport(auth, sport_id, request)
    await session.commit()
    return Response(status_code=204)


# --- Catalog units ---


@router.get("/units")
async def list_units(
    _auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    sport_id: uuid.UUID | None = Query(default=None),  # noqa: B008
    include_inactive: bool = Query(default=True),
) -> dict[str, Any]:
    units = await _service(session).list_units(sport_id=sport_id, include_inactive=include_inactive)
    return {"data": [CatalogUnitResponse.model_validate(unit) for unit in units]}


@router.post("/units", status_code=201)
async def create_unit(
    data: CatalogUnitCreate,
    request: Request,
    auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    unit = await _service(session).create_unit(auth, data, request)
    await session.commit()
    return {"data": CatalogUnitResponse.model_validate(unit)}


@router.patch("/units/{unit_id}")
async def update_unit(
    unit_id: uuid.UUID,
    data: CatalogUnitUpdate,
    request: Request,
    auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    unit = await _service(session).update_unit(auth, unit_id, data, request)
    await session.commit()
    return {"data": CatalogUnitResponse.model_validate(unit)}


@router.delete("/units/{unit_id}", status_code=204)
async def delete_unit(
    unit_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> Response:
    await _service(session).delete_unit(auth, unit_id, request)
    await session.commit()
    return Response(status_code=204)


# --- Catalog disciplines ---


@router.get("/disciplines")
async def list_disciplines(
    _auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100),
    sport_id: uuid.UUID | None = Query(default=None),  # noqa: B008
    federation: str | None = Query(default=None),
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    include_inactive: bool = Query(default=True),
) -> dict[str, Any]:
    disciplines, total = await _service(session).list_disciplines(
        offset=(page - 1) * per_page,
        limit=per_page,
        sport_id=sport_id,
        federation=federation,
        category=category,
        search=search,
        include_inactive=include_inactive,
    )
    return {
        "data": [CatalogDisciplineResponse.model_validate(d) for d in disciplines],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if per_page else 0,
        },
    }


@router.post("/disciplines", status_code=201)
async def create_discipline(
    data: CatalogDisciplineCreate,
    request: Request,
    auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    discipline = await _service(session).create_discipline(auth, data, request)
    await session.commit()
    return {"data": CatalogDisciplineResponse.model_validate(discipline)}


@router.patch("/disciplines/{discipline_id}")
async def update_discipline(
    discipline_id: uuid.UUID,
    data: CatalogDisciplineUpdate,
    request: Request,
    auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    discipline = await _service(session).update_discipline(auth, discipline_id, data, request)
    await session.commit()
    return {"data": CatalogDisciplineResponse.model_validate(discipline)}


@router.delete("/disciplines/{discipline_id}", status_code=204)
async def delete_discipline(
    discipline_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(require_platform_admin),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> Response:
    await _service(session).delete_discipline(auth, discipline_id, request)
    await session.commit()
    return Response(status_code=204)
