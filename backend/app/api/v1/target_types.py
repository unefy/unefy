from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.target_type_seeds import CALIBERS
from app.database import get_db_session
from app.dependencies import AuthContext, get_current_user
from app.repositories.target_type import TargetTypeRepository
from app.schemas.target_type import CaliberResponse, TargetTypeResponse

router = APIRouter()


@router.get("")
async def list_target_types(
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    include_inactive: bool = Query(default=False),
) -> dict[str, Any]:
    """Ring geometry of every target the clients can score against.

    Readable by any signed-in member: it is federation reference data, not club
    data. `include_inactive` exists for the admin view — targets whose numbers
    have not been verified are seeded inactive and must stay out of the picker.
    """
    repo = TargetTypeRepository(session)
    rows = await repo.get_all(include_inactive=include_inactive)
    return {"data": [TargetTypeResponse.model_validate(r).model_dump(mode="json") for r in rows]}


@router.get("/calibers")
async def list_calibers(
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    """Bullet diameters for the caliber picker.

    A constant, not a table: the list changes on the timescale of decades, and a
    series may always send a free-form `caliber_mm` instead.
    """
    return {"data": [CaliberResponse.model_validate(c).model_dump(mode="json") for c in CALIBERS]}
