import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database import get_db_session
from app.dependencies import AuthContext, get_current_user, require_role
from app.schemas.function import FunctionCreate, FunctionResponse, FunctionUpdate
from app.services.function import FunctionService

router = APIRouter()


@router.get("")
async def list_functions(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    include_inactive: bool = Query(default=False),
) -> dict[str, Any]:
    """The club's list of offices. Board included: assigning needs the list."""
    service = FunctionService(session, auth.tenant)
    functions = await service.functions.get_all(include_inactive=include_inactive)
    return {"data": [FunctionResponse.model_validate(f).model_dump(mode="json") for f in functions]}


@router.get("/holders")
async def list_holders(
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    at: date | None = Query(default=None),  # noqa: B008
) -> dict[str, Any]:
    """Who holds which office at the given date (default: today).

    Readable by every member — the board list is public within a club.
    """
    service = FunctionService(session, auth.tenant)
    holders = await service.holders(at or date.today())
    return {"data": [h.model_dump(mode="json") for h in holders]}


@router.post("", status_code=201)
async def create_function(
    data: FunctionCreate,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Create a club-owned function."""
    service = FunctionService(session, auth.tenant)
    function = await service.create_function(data, created_by=auth.user_id)
    return {"data": FunctionResponse.model_validate(function).model_dump(mode="json")}


@router.patch("/{function_id}")
async def update_function(
    function_id: uuid.UUID,
    data: FunctionUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Update a club-owned function."""
    service = FunctionService(session, auth.tenant)
    function = await service.update_function(function_id, data, updated_by=auth.user_id)
    if function is None:
        raise NotFoundError("Function not found")
    return {"data": FunctionResponse.model_validate(function).model_dump(mode="json")}


@router.delete("/{function_id}", status_code=204)
async def delete_function(
    function_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> None:
    """Delete a function without assignments; 409 once terms exist."""
    service = FunctionService(session, auth.tenant)
    await service.delete_function(function_id)
