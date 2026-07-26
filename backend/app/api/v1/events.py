import math
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database import get_db_session
from app.dependencies import AuthContext, require_role
from app.schemas.event import (
    EventCreate,
    EventRegistrationCreate,
    EventRegistrationResponse,
    EventResponse,
    EventUpdate,
)
from app.services.event import EventService

router = APIRouter()


def _get_service(session: AsyncSession, auth: AuthContext) -> EventService:
    return EventService(session, auth.tenant_id)


@router.get("")
async def list_events(
    auth: AuthContext = Depends(require_role("owner", "admin", "board", "member")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    event_type: str | None = Query(default=None),
    starts_after: datetime | None = Query(default=None),  # noqa: B008
    starts_before: datetime | None = Query(default=None),  # noqa: B008
    competition_id: uuid.UUID | None = Query(default=None),  # noqa: B008
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
) -> dict:
    """List events with registration counts."""
    service = _get_service(session, auth)
    offset = (page - 1) * per_page
    rows = await service.events.get_all(
        offset=offset,
        limit=per_page,
        event_type=event_type,
        starts_after=starts_after,
        starts_before=starts_before,
        competition_id=competition_id,
        sort_order=sort_order,
    )
    total = await service.events.count(
        event_type=event_type,
        starts_after=starts_after,
        starts_before=starts_before,
        competition_id=competition_id,
    )
    return {
        "data": [
            EventResponse.model_validate(event).model_dump(mode="json")
            | {"registered_count": count, "competition_name": competition_name}
            for event, count, competition_name in rows
        ],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total > 0 else 1,
        },
    }


@router.get("/{event_id}")
async def get_event(
    event_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board", "member")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict:
    """Get a single event with its registrations."""
    service = _get_service(session, auth)
    event = await service.events.get_by_id(event_id)
    if event is None:
        raise NotFoundError("Event not found")

    rows = await service.registrations.get_for_event(event_id)
    registered_count = sum(1 for r, _f, _l in rows if r.status == "registered")
    return {
        "data": EventResponse.model_validate(event).model_dump(mode="json")
        | {
            "registered_count": registered_count,
            "competition_name": await service.competition_name(event),
            "registrations": [
                EventRegistrationResponse.model_validate(r).model_dump(mode="json")
                | {"member_name": f"{first} {last}"}
                for r, first, last in rows
            ],
        }
    }


@router.post("", status_code=201)
async def create_event(
    data: EventCreate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict:
    """Create a new event."""
    service = _get_service(session, auth)
    event = await service.create(data, created_by=auth.user_id)
    return {
        "data": EventResponse.model_validate(event).model_dump(mode="json")
        | {"registered_count": 0, "competition_name": await service.competition_name(event)}
    }


@router.patch("/{event_id}")
async def update_event(
    event_id: uuid.UUID,
    data: EventUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict:
    """Update an event."""
    service = _get_service(session, auth)
    event = await service.update(event_id, data, updated_by=auth.user_id)
    if event is None:
        raise NotFoundError("Event not found")
    registered_count = await service.registrations.count_registered(event_id)
    return {
        "data": EventResponse.model_validate(event).model_dump(mode="json")
        | {
            "registered_count": registered_count,
            "competition_name": await service.competition_name(event),
        }
    }


@router.delete("/{event_id}", status_code=204)
async def delete_event(
    event_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> None:
    """Soft-delete an event."""
    service = _get_service(session, auth)
    deleted = await service.events.soft_delete(event_id)
    if not deleted:
        raise NotFoundError("Event not found")


@router.post("/{event_id}/registrations", status_code=201)
async def register_member(
    event_id: uuid.UUID,
    data: EventRegistrationCreate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict:
    """Register a member for an event (waitlist when full)."""
    service = _get_service(session, auth)
    registration = await service.register(event_id, data, created_by=auth.user_id)
    return {"data": EventRegistrationResponse.model_validate(registration).model_dump(mode="json")}


@router.delete("/{event_id}/registrations/{registration_id}", status_code=204)
async def unregister_member(
    event_id: uuid.UUID,
    registration_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> None:
    """Remove a registration; first waitlisted member is promoted."""
    service = _get_service(session, auth)
    deleted = await service.unregister(event_id, registration_id)
    if not deleted:
        raise NotFoundError("Registration not found")
