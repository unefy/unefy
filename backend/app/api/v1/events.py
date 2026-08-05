import math
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.preconditions import require_if_match, set_etag
from app.database import get_db_session
from app.dependencies import AuthContext, get_current_user, require_role
from app.models.member import Member
from app.schemas.attendance import AttendanceSessionResponse
from app.schemas.event import (
    EventCreate,
    EventRegistrationCreate,
    EventRegistrationResponse,
    EventResponse,
    EventUpdate,
)
from app.services.attendance import AttendanceService
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
    response: Response,
    auth: AuthContext = Depends(require_role("owner", "admin", "board", "member")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Get a single event with its registrations."""
    service = _get_service(session, auth)
    event = await service.events.get_by_id(event_id)
    if event is None:
        raise NotFoundError("Event not found")
    set_etag(response, event)

    rows = await service.registrations.get_for_event(event_id)
    registered_count = sum(1 for r, _f, _l in rows if r.status == "registered")
    # Same semantics as the list endpoint: any registration counts, waitlisted
    # included — the caller's question is "am I on this event", not "am I in".
    own_member = await service.members.get_by_user_id(auth.user_id)

    # The attendance sessions hung off this event — the second door to the
    # attendance list: whoever opens the training evening in the calendar can
    # step through to who was there. Board only, matching the attendance API
    # itself: attendance is a record of where people were, and even the
    # session's existence and head count belong to that record, not to every
    # member browsing the calendar.
    attendance_sessions: list[dict[str, Any]] = []
    if auth.role in ("owner", "admin", "board"):
        attendance = AttendanceService(session, auth)
        attendance_sessions = [
            AttendanceSessionResponse.model_validate(row).model_dump(mode="json")
            | {"record_count": count, "event_title": event.title}
            for row, count in await attendance.sessions.for_event(event_id)
        ]

    return {
        "data": EventResponse.model_validate(event).model_dump(mode="json")
        | {
            "registered_count": registered_count,
            "competition_name": await service.competition_name(event),
            "is_registered": own_member is not None
            and any(r.member_id == own_member.id for r, _f, _l in rows),
            "registrations": [
                EventRegistrationResponse.model_validate(r).model_dump(mode="json")
                | {"member_name": f"{first} {last}"}
                for r, first, last in rows
            ],
            "attendance_sessions": attendance_sessions,
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
    request: Request,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Update an event. Honours If-Match — absent, last write wins as ever."""
    service = _get_service(session, auth)
    existing = await service.events.get_by_id(event_id)
    if existing is None:
        raise NotFoundError("Event not found")
    require_if_match(
        request, existing, EventResponse.model_validate(existing).model_dump(mode="json")
    )

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
    request: Request,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> None:
    """Soft-delete an event. Honours If-Match."""
    service = _get_service(session, auth)
    existing = await service.events.get_by_id(event_id)
    if existing is not None:
        require_if_match(
            request, existing, EventResponse.model_validate(existing).model_dump(mode="json")
        )
    deleted = await service.events.soft_delete(event_id)
    if not deleted:
        raise NotFoundError("Event not found")


@router.post("/{event_id}/attendance-session")
async def open_attendance_session(
    event_id: uuid.UUID,
    response: Response,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """The event's open attendance session — found or freshly opened.

    One button on the event: "start attendance". Idempotent, because that
    button gets double-tapped; an existing open session comes back with 200
    instead of a conflict, since either way the caller's next step is the same
    — start checking people in. A deliberate second session for the same
    evening (two ranges) goes through the plain attendance API.
    """
    service = _get_service(session, auth)
    event = await service.events.get_by_id(event_id)
    if event is None:
        raise NotFoundError("Event not found")

    attendance = AttendanceService(session, auth)
    row, created = await attendance.open_session_for_event(event)
    response.status_code = 201 if created else 200
    return {
        "data": AttendanceSessionResponse.model_validate(row).model_dump(mode="json")
        | {
            "record_count": await attendance.sessions.record_count(row.id),
            "supervisor_name": await attendance.sessions.supervisor_name(row),
            "event_title": event.title,
        }
    }


@router.post("/{event_id}/registrations", status_code=201)
async def register_member(
    event_id: uuid.UUID,
    data: EventRegistrationCreate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Register a member for an event (waitlist when full).

    Board-level, so the registration deadline does not apply: adding someone
    after it closed is the normal favour, not a bypass.
    """
    service = _get_service(session, auth)
    registration = await service.register(
        event_id, data, created_by=auth.user_id, enforce_deadline=False
    )
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
