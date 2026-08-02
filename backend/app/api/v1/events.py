import math
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database import get_db_session
from app.dependencies import AuthContext, get_current_user, require_role
from app.models.member import Member
from app.schemas.event import (
    EventCreate,
    EventRegistrationCreate,
    EventRegistrationResponse,
    EventResponse,
    EventUpdate,
)
from app.services.event import EventService

router = APIRouter()


async def _own_member(service: EventService, auth: AuthContext) -> Member:
    """The caller's own member record, or 404 when the account has none."""
    member = await service.members.get_by_user_id(auth.user_id)
    if member is None:
        raise NotFoundError("No member record is linked to this account")
    return member


def _get_service(session: AsyncSession, auth: AuthContext) -> EventService:
    return EventService(session, auth.tenant)


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
) -> dict[str, Any]:
    """List events with registration counts."""
    service = _get_service(session, auth)
    offset = (page - 1) * per_page
    rows = await service.events.list_with_counts(
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
    # Whether the caller is on each event. Without this the mobile app cannot
    # tell "register" from "cancel" and has to guess from local state.
    own_member = await service.members.get_by_user_id(auth.user_id)
    registered_ids: set[uuid.UUID] = set()
    if own_member is not None:
        registered_ids = await service.registrations.registered_event_ids_for_member(
            own_member.id, [event.id for event, _, _ in rows]
        )

    return {
        "data": [
            EventResponse.model_validate(event).model_dump(mode="json")
            | {
                "registered_count": count,
                "competition_name": competition_name,
                "is_registered": event.id in registered_ids,
            }
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
) -> dict[str, Any]:
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
) -> dict[str, Any]:
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
) -> dict[str, Any]:
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
) -> dict[str, Any]:
    """Register a member for an event (waitlist when full)."""
    service = _get_service(session, auth)
    registration = await service.register(event_id, data, created_by=auth.user_id)
    return {"data": EventRegistrationResponse.model_validate(registration).model_dump(mode="json")}


@router.post("/{event_id}/registrations/me", status_code=201)
async def register_self(
    event_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Register the caller for an event.

    The member_id comes from the caller's own linked record, never from the
    request body — that is the whole difference to the board-level endpoint
    above, which registers someone else. Declared before the `{registration_id}`
    route, which would reject "me" as a non-UUID.
    """
    service = _get_service(session, auth)
    member = await _own_member(service, auth)
    registration = await service.register(
        event_id, EventRegistrationCreate(member_id=member.id), created_by=auth.user_id
    )
    return {"data": EventRegistrationResponse.model_validate(registration).model_dump(mode="json")}


@router.delete("/{event_id}/registrations/me", status_code=204)
async def unregister_self(
    event_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> None:
    """Cancel the caller's own registration."""
    service = _get_service(session, auth)
    member = await _own_member(service, auth)
    registration = await service.registrations.get_by_event_and_member(event_id, member.id)
    if registration is None:
        raise NotFoundError("You are not registered for this event")
    deleted = await service.unregister(event_id, registration.id)
    if not deleted:
        raise NotFoundError("Registration not found")


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
