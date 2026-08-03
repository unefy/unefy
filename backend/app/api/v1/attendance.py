import math
import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database import get_db_session
from app.dependencies import AuthContext, get_current_user, require_role
from app.models.attendance import AttendanceRecord
from app.schemas.attendance import (
    REASON_MIN_LENGTH,
    AttendanceCheckIn,
    AttendanceRecordResponse,
    AttendanceRecordUpdate,
    AttendanceScanCheckIn,
    AttendanceSeedResponse,
    AttendanceSessionCreate,
    AttendanceSessionResponse,
    AttendanceSessionUpdate,
    AuditEntryResponse,
    MemberAttendanceRecordResponse,
)
from app.services.attendance import RECORD_TARGET, SESSION_TARGET, AttendanceService
from app.services.audit import list_tenant_audit

router = APIRouter()

# Attendance is a record of where a person was on which evening. Reading it is
# therefore restricted to the board, not open to every member — a member sees
# their own history through `/attendance/me/records` and nothing else.
require_board = require_role("owner", "admin", "board")


def _get_service(session: AsyncSession, auth: AuthContext) -> AttendanceService:
    return AttendanceService(session, auth)


def _audit_payload(entry: object, actor_name: str | None) -> dict[str, Any]:
    return AuditEntryResponse.model_validate(entry).model_dump(mode="json") | {
        "actor_name": actor_name
    }


def _session_payload(
    row: object, *, record_count: int, supervisor_name: str | None
) -> dict[str, Any]:
    return AttendanceSessionResponse.model_validate(row).model_dump(mode="json") | {
        "record_count": record_count,
        "supervisor_name": supervisor_name,
    }


# --- Sessions ---


@router.post("/sessions", status_code=201)
async def create_session(
    data: AttendanceSessionCreate,
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Open a window during which members can be checked in."""
    service = _get_service(session, auth)
    row = await service.create_session(data)
    return {
        "data": _session_payload(
            row,
            record_count=0,
            supervisor_name=await service.sessions.supervisor_name(row),
        )
    }


@router.get("/sessions")
async def list_sessions(
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    opens_after: datetime | None = Query(default=None),  # noqa: B008
    opens_before: datetime | None = Query(default=None),  # noqa: B008
    division_id: uuid.UUID | None = Query(default=None),  # noqa: B008
    status: str | None = Query(default=None, pattern="^(open|closed)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> dict[str, Any]:
    """List attendance sessions, newest first."""
    service = _get_service(session, auth)
    filters = {
        "opens_after": opens_after,
        "opens_before": opens_before,
        "division_id": division_id,
        "status": status,
    }
    rows = await service.sessions.list_with_counts(
        offset=(page - 1) * per_page,
        limit=per_page,
        sort_order=sort_order,
        **filters,  # type: ignore[arg-type]
    )
    total = await service.sessions.count(**filters)  # type: ignore[arg-type]
    return {
        "data": [
            _session_payload(row, record_count=count, supervisor_name=supervisor)
            for row, count, supervisor in rows
        ],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total > 0 else 1,
        },
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: uuid.UUID,
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """A single session with its attendance list."""
    service = _get_service(session, auth)
    row = await service.get_session(session_id)
    records = await service.records.get_for_session(session_id)
    return {
        "data": _session_payload(
            row,
            record_count=len(records),
            supervisor_name=await service.sessions.supervisor_name(row),
        )
        | {
            "records": [
                AttendanceRecordResponse.model_validate(record).model_dump(mode="json")
                | _display_name(record, first, last, number)
                for record, first, last, number in records
            ]
        }
    }


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: uuid.UUID,
    data: AttendanceSessionUpdate,
    request: Request,
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Change an open session. Audited; rejected once the session is closed."""
    service = _get_service(session, auth)
    row = await service.update_session(session_id, data, request=request)
    return {
        "data": _session_payload(
            row,
            record_count=await service.sessions.record_count(session_id),
            supervisor_name=await service.sessions.supervisor_name(row),
        )
    }


@router.post("/sessions/{session_id}/close")
async def close_session(
    session_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Freeze a session: no further check-ins and no corrections.

    There is no reopen endpoint, and that is the feature — an appointment added
    after the fact must be impossible, not merely visible.
    """
    service = _get_service(session, auth)
    row = await service.close_session(session_id, request=request)
    return {
        "data": _session_payload(
            row,
            record_count=await service.sessions.record_count(session_id),
            supervisor_name=await service.sessions.supervisor_name(row),
        )
    }


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: uuid.UUID,
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    reason: str = Query(min_length=REASON_MIN_LENGTH, max_length=1000),
) -> None:
    """Remove a session that was created by mistake. Only while empty and open."""
    service = _get_service(session, auth)
    await service.delete_session(session_id, reason=reason)


@router.get("/sessions/{session_id}/records")
async def list_session_records(
    session_id: uuid.UUID,
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """The attendance list of one session."""
    service = _get_service(session, auth)
    await service.get_session(session_id)
    records = await service.records.get_for_session(session_id)
    return {
        "data": [
            AttendanceRecordResponse.model_validate(record).model_dump(mode="json")
            | _display_name(record, first, last, number)
            for record, first, last, number in records
        ]
    }


@router.get("/sessions/{session_id}/audit")
async def get_session_audit(
    session_id: uuid.UUID,
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """The trail of this session and of every record in it, oldest first.

    One list rather than one per row: what happened during an evening is a
    single story, and it reads as one. Answers for deleted sessions and
    corrected-away records too — a trail that disappears with its subject
    proves nothing.
    """
    service = _get_service(session, auth)
    await service.require_session_exists(session_id)
    entries = await list_tenant_audit(
        session,
        service.tenant_id,
        targets={
            SESSION_TARGET: [session_id],
            RECORD_TARGET: await service.records.all_ids_for_session(session_id),
        },
    )
    return {"data": [_audit_payload(entry, actor) for entry, actor in entries]}


# --- Check-in ---


@router.post("/sessions/{session_id}/check-in", status_code=201)
async def check_in(
    session_id: uuid.UUID,
    data: AttendanceCheckIn,
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Check a member in — the supervisor ticking the box.

    The caller supplies who, nothing else: the time is the server's and the
    assurance level follows from the method.
    """
    service = _get_service(session, auth)
    record = await service.check_in(session_id, data)
    return {"data": await _record_with_member(service, record)}


@router.post("/sessions/{session_id}/scan", status_code=201)
async def check_in_by_code(
    session_id: uuid.UUID,
    data: AttendanceScanCheckIn,
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Check a member in from their rotating code.

    Its own endpoint rather than a branch of `check-in`: this path proves the
    person cryptographically and rates `high`, while the other rates `low`
    because a human asserted it. Same board authorisation either way — the code
    proves who the member is, not that the scanner is entitled to check anyone
    in, and that second half is what the session's supervisor is for.
    """
    service = _get_service(session, auth)
    record = await service.check_in_by_code(session_id, data)
    return {"data": await _record_with_member(service, record)}


def _display_name(
    record: AttendanceRecord, first: str | None, last: str | None, number: str | None
) -> dict[str, Any]:
    """Name and number for one row, member or guest.

    A guest has no member row, so the outer join hands back nulls — formatting
    those straight into a string produced "None None" on screen.
    """
    if record.member_id is None:
        return {"member_name": record.guest_name, "member_number": None}
    return {"member_name": f"{first} {last}", "member_number": number}


async def _record_with_member(
    service: AttendanceService, record: AttendanceRecord
) -> dict[str, Any]:
    """A record with the member's name filled in.

    The scanner shows this straight back to the supervisor, and "checked in"
    without a name is useless to someone watching a queue go past — they cannot
    tell whether the person in front of them is the one that just registered.
    """
    payload = AttendanceRecordResponse.model_validate(record).model_dump(mode="json")
    if record.member_id is None:
        # A guest is named by the record itself; there is nothing to look up.
        return payload | {"member_name": record.guest_name, "member_number": None}

    member = await service.members.get_by_id(record.member_id)
    if member is not None:
        payload |= {
            "member_name": f"{member.first_name} {member.last_name}",
            "member_number": member.member_number,
        }
    return payload


@router.post("/records/{record_id}/check-out")
async def check_out(
    record_id: uuid.UUID,
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Record that a member has left."""
    service = _get_service(session, auth)
    record = await service.check_out(record_id)
    return {"data": AttendanceRecordResponse.model_validate(record).model_dump(mode="json")}


@router.patch("/records/{record_id}")
async def update_record(
    record_id: uuid.UUID,
    data: AttendanceRecordUpdate,
    request: Request,
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Correct a record. Requires a reason and writes an audit entry."""
    service = _get_service(session, auth)
    record = await service.update_record(record_id, data, request=request)
    return {"data": AttendanceRecordResponse.model_validate(record).model_dump(mode="json")}


@router.delete("/records/{record_id}", status_code=204)
async def delete_record(
    record_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    reason: str | None = Query(default=None, min_length=REASON_MIN_LENGTH, max_length=1000),
) -> None:
    """Soft-delete a record into the audit trail.

    The reason is optional, and only because this endpoint cannot be reached
    after the session is closed. Inside an open session a removal is almost
    always a supervisor undoing a mistap seconds ago, and demanding prose for
    that produces "x" and "Fehler" — which devalues the reasons on the entries
    where one actually matters. What makes an undo verifiable is the audit
    entry's own actor and timestamp, not a sentence the client supplied.
    """
    service = _get_service(session, auth)
    await service.delete_record(record_id, reason=reason, request=request)


@router.get("/records/{record_id}/audit")
async def get_record_audit(
    record_id: uuid.UUID,
    auth: AuthContext = Depends(require_board),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """The trail of corrections to this record, oldest first.

    Deliberately readable after the record has been corrected away: that is
    exactly when someone needs to know what happened to it.
    """
    service = _get_service(session, auth)
    await service.require_record_exists(record_id)
    entries = await list_tenant_audit(
        session, service.tenant_id, targets={RECORD_TARGET: [record_id]}
    )
    return {"data": [_audit_payload(entry, actor) for entry, actor in entries]}


# --- Member self-service ---


@router.get("/me/seed")
async def get_my_seed(
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """The seed a member's app computes its rotating code from.

    Any member, not board only: this is the member's own credential. It is
    handed out for 24 hours at a time so the app keeps working in a basement
    with no signal, which is where shooting ranges tend to be.
    """
    service = _get_service(session, auth)
    member = await service.members.get_by_user_id(auth.user_id)
    if member is None:
        raise NotFoundError("No member record is linked to this account")
    seed = await service.member_seed(member)
    return {"data": AttendanceSeedResponse.model_validate(seed).model_dump(mode="json")}


@router.get("/me/records")
async def list_my_records(
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    from_date: date | None = Query(default=None),  # noqa: B008
    to_date: date | None = Query(default=None),  # noqa: B008
) -> dict[str, Any]:
    """A member's own attendance history — the Art. 15 access path."""
    service = _get_service(session, auth)
    member = await service.members.get_by_user_id(auth.user_id)
    if member is None:
        raise NotFoundError("No member record is linked to this account")
    return await member_records_payload(service, member.id, page, per_page, from_date, to_date)


async def member_records_payload(
    service: AttendanceService,
    member_id: uuid.UUID,
    page: int,
    per_page: int,
    from_date: date | None,
    to_date: date | None,
) -> dict[str, Any]:
    rows = await service.records.get_for_member(
        member_id,
        offset=(page - 1) * per_page,
        limit=per_page,
        from_date=from_date,
        to_date=to_date,
    )
    total = await service.records.count_for_member(member_id, from_date=from_date, to_date=to_date)
    return {
        "data": [
            MemberAttendanceRecordResponse.model_validate(record).model_dump(mode="json")
            | {"session_title": title, "session_location": location}
            for record, title, location in rows
        ],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total > 0 else 1,
        },
    }


# The board's view of one member's history lives on the members router
# (`GET /api/v1/members/{id}/attendance`), where callers will look for it.
