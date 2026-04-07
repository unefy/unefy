import math
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.rate_limit import RateLimit
from app.database import get_db_session
from app.dependencies import AuthContext, require_role
from app.repositories.event import EventRepository, ResultRepository
from app.schemas.event import (
    EventCreate,
    EventResponse,
    EventUpdate,
    ResultCreate,
    ResultResponse,
    ResultUpdate,
)

router = APIRouter()


# --- Helpers ---


def _event_repo(session: AsyncSession, auth: AuthContext) -> EventRepository:
    return EventRepository(session, auth.tenant_id)


def _result_repo(session: AsyncSession, auth: AuthContext, event_id: uuid.UUID) -> ResultRepository:
    return ResultRepository(session, auth.tenant_id, event_id)


def _event_response(event: Any) -> dict[str, Any]:
    return EventResponse.model_validate(event).model_dump(mode="json")


def _result_response(result: Any) -> dict[str, Any]:
    return ResultResponse.model_validate(result).model_dump(mode="json")


# --- Events CRUD ---


@router.get("")
async def list_events(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="date", pattern="^(date|name|event_type|created_at)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> dict[str, Any]:
    repo = _event_repo(session, auth)
    offset = (page - 1) * per_page
    items = await repo.get_all(
        offset=offset, limit=per_page, sort_by=sort_by, sort_order=sort_order
    )
    total = await repo.count()
    return {
        "data": [_event_response(e) for e in items],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, math.ceil(total / per_page)),
        },
    }


@router.post("", dependencies=[Depends(RateLimit(limit=30, window=60, scope="event-create"))])
async def create_event(
    data: EventCreate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    repo = _event_repo(session, auth)
    event = await repo.create(data)
    return {"data": _event_response(event)}


@router.get("/{event_id}")
async def get_event(
    event_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    repo = _event_repo(session, auth)
    event = await repo.get_by_id(event_id)
    if event is None:
        raise NotFoundError("Event not found")
    return {"data": _event_response(event)}


@router.patch("/{event_id}")
async def update_event(
    event_id: uuid.UUID,
    data: EventUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    repo = _event_repo(session, auth)
    event = await repo.update(event_id, data)
    if event is None:
        raise NotFoundError("Event not found")
    return {"data": _event_response(event)}


@router.delete("/{event_id}")
async def delete_event(
    event_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    repo = _event_repo(session, auth)
    deleted = await repo.soft_delete(event_id)
    if not deleted:
        raise NotFoundError("Event not found")
    return {"data": {"message": "Event deleted"}}


# --- Results (scoped under /events/{event_id}/results) ---


@router.get("/{event_id}/results")
async def list_results(
    event_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=500),
    member_id: uuid.UUID | None = Query(default=None),  # noqa: B008
) -> dict[str, Any]:
    # Verify event exists + belongs to tenant.
    event_repo = _event_repo(session, auth)
    if await event_repo.get_by_id(event_id) is None:
        raise NotFoundError("Event not found")

    repo = _result_repo(session, auth, event_id)
    offset = (page - 1) * per_page
    items = await repo.get_all(offset=offset, limit=per_page, member_id=member_id)
    total = await repo.count(member_id=member_id)
    return {
        "data": [_result_response(r) for r in items],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, math.ceil(total / per_page)),
        },
    }


@router.post(
    "/{event_id}/results",
    dependencies=[Depends(RateLimit(limit=60, window=60, scope="result-create"))],
)
async def create_result(
    event_id: uuid.UUID,
    data: ResultCreate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Create a shooting result. Idempotent: if a result with the same id
    already exists in this tenant+event, it is returned as-is."""
    event_repo = _event_repo(session, auth)
    if await event_repo.get_by_id(event_id) is None:
        raise NotFoundError("Event not found")

    repo = _result_repo(session, auth, event_id)
    result, _created = await repo.create_idempotent(data, recorded_by=auth.user_id)
    return {"data": _result_response(result)}


@router.get("/{event_id}/results/{result_id}")
async def get_result(
    event_id: uuid.UUID,
    result_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    repo = _result_repo(session, auth, event_id)
    result = await repo.get_by_id(result_id)
    if result is None:
        raise NotFoundError("Result not found")
    return {"data": _result_response(result)}


@router.patch("/{event_id}/results/{result_id}")
async def update_result(
    event_id: uuid.UUID,
    result_id: uuid.UUID,
    data: ResultUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    repo = _result_repo(session, auth, event_id)
    result = await repo.update(result_id, data)
    if result is None:
        raise NotFoundError("Result not found")
    return {"data": _result_response(result)}


@router.delete("/{event_id}/results/{result_id}")
async def delete_result(
    event_id: uuid.UUID,
    result_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    repo = _result_repo(session, auth, event_id)
    deleted = await repo.delete(result_id)
    if not deleted:
        raise NotFoundError("Result not found")
    return {"data": {"message": "Result deleted"}}
