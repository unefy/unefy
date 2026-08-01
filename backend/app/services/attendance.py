import uuid
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.dependencies import AuthContext
from app.models.attendance import ASSURANCE_BY_METHOD, AttendanceRecord, AttendanceSession
from app.models.tenant import Tenant
from app.repositories.attendance import (
    AttendanceRecordRepository,
    AttendanceSessionRepository,
)
from app.repositories.member import MemberRepository
from app.schemas.attendance import (
    AttendanceCheckIn,
    AttendanceRecordUpdate,
    AttendanceSessionCreate,
    AttendanceSessionUpdate,
)
from app.services.audit import diff, jsonable, record_tenant_action

logger = structlog.get_logger()

SESSION_TARGET = "attendance_session"
RECORD_TARGET = "attendance_record"


class AttendanceService:
    """Attendance sessions and records — the evidence layer of the core.

    Two rules run through everything here:

    1. A closed session is frozen. No check-ins, no corrections, no reopening.
       That is the whole point of closing: a late entry must be impossible, not
       merely visible.
    2. Every change to an existing record leaves an audit entry with a human
       reason. The record answers "who was there"; the audit trail answers
       "how do you know".
    """

    def __init__(self, session: AsyncSession, auth: AuthContext) -> None:
        self.session = session
        self.auth = auth
        self.tenant_id = auth.tenant
        self.sessions = AttendanceSessionRepository(session, self.tenant_id)
        self.records = AttendanceRecordRepository(session, self.tenant_id)
        self.members = MemberRepository(session, self.tenant_id)

    # --- Sessions ---

    async def club_timezone(self) -> ZoneInfo:
        """The club's own zone, read fresh rather than cached.

        Read from the database instead of a constant: a check-in's calendar day
        is a claim about the club's evening, not about the server's clock, and
        the two differ for every session that runs past midnight.
        """
        result = await self.session.execute(
            select(Tenant.timezone).where(Tenant.id == self.tenant_id)
        )
        name = result.scalar_one_or_none()
        try:
            return ZoneInfo(name) if name else ZoneInfo("UTC")
        except (ZoneInfoNotFoundError, ValueError):
            # A club whose zone became unresolvable (a renamed IANA zone, say)
            # must still be able to record attendance. UTC is wrong by at most
            # a couple of hours; refusing the check-in loses the evening.
            logger.warning(
                "tenant_timezone_unresolvable", tenant_id=str(self.tenant_id), timezone=name
            )
            return ZoneInfo("UTC")

    async def get_session(self, session_id: uuid.UUID) -> AttendanceSession:
        row = await self.sessions.get_by_id(session_id)
        if row is None:
            raise NotFoundError("Attendance session not found")
        return row

    async def _require_open(self, row: AttendanceSession) -> None:
        if row.status == "closed":
            raise ConflictError("Attendance session is closed. Closed sessions cannot be changed.")

    async def _validate_supervisor(self, member_id: uuid.UUID | None) -> None:
        if member_id is None:
            return
        if await self.members.get_by_id(member_id) is None:
            raise NotFoundError("Supervisor member not found")

    async def create_session(self, data: AttendanceSessionCreate) -> AttendanceSession:
        await self._validate_supervisor(data.supervisor_member_id)
        row = AttendanceSession(
            **data.model_dump(),
            tenant_id=self.tenant_id,
            status="open",
            created_by=self.auth.user_id,
            updated_by=self.auth.user_id,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def update_session(
        self,
        session_id: uuid.UUID,
        data: AttendanceSessionUpdate,
        *,
        request: Request | None = None,
    ) -> AttendanceSession:
        row = await self.get_session(session_id)
        await self._require_open(row)

        changes = data.model_dump(exclude_unset=True, exclude={"reason"})
        if "supervisor_member_id" in changes:
            await self._validate_supervisor(changes["supervisor_member_id"])

        before = {field: getattr(row, field) for field in changes}
        for field, value in changes.items():
            setattr(row, field, value)
        if row.closes_at <= row.opens_at:
            raise ValidationError("closes_at must be after opens_at")
        row.updated_by = self.auth.user_id
        await self.session.flush()

        applied = diff(before, changes)
        if applied:
            await record_tenant_action(
                self.session,
                self.auth,
                f"{SESSION_TARGET}.updated",
                target_type=SESSION_TARGET,
                target_id=row.id,
                request=request,
                changes=applied,
                reason=data.reason,
            )
        await self.session.refresh(row)
        return row

    async def close_session(
        self, session_id: uuid.UUID, *, request: Request | None = None
    ) -> AttendanceSession:
        """Freeze a session. Irreversible by design — there is no reopen path."""
        row = await self.get_session(session_id)
        if row.status == "closed":
            raise ConflictError("Attendance session is already closed")

        record_count = await self.sessions.record_count(session_id)
        row.status = "closed"
        row.closed_at = datetime.now(UTC)
        row.closed_by = self.auth.user_id
        row.updated_by = self.auth.user_id
        await self.session.flush()

        # The count is part of the entry so that a later dispute can be settled
        # against what was frozen, not only against what the table holds now.
        await record_tenant_action(
            self.session,
            self.auth,
            f"{SESSION_TARGET}.closed",
            target_type=SESSION_TARGET,
            target_id=row.id,
            request=request,
            changes={"record_count": record_count},
        )
        await self.session.refresh(row)
        return row

    async def delete_session(self, session_id: uuid.UUID, *, reason: str) -> None:
        row = await self.get_session(session_id)
        await self._require_open(row)
        if await self.sessions.record_count(session_id) > 0:
            raise ConflictError(
                "Attendance session has records. Remove them individually, "
                "so every removal carries its own reason."
            )
        await self.sessions.soft_delete(session_id)
        await record_tenant_action(
            self.session,
            self.auth,
            f"{SESSION_TARGET}.deleted",
            target_type=SESSION_TARGET,
            target_id=session_id,
            reason=reason,
        )

    # --- Check-in ---

    async def check_in(self, session_id: uuid.UUID, data: AttendanceCheckIn) -> AttendanceRecord:
        row = await self.get_session(session_id)
        await self._require_open(row)

        if await self.members.get_by_id(data.member_id) is None:
            raise NotFoundError("Member not found")
        if await self.records.get_active(session_id, data.member_id) is not None:
            raise ConflictError("Member is already checked in for this session")

        record = AttendanceRecord(
            tenant_id=self.tenant_id,
            session_id=session_id,
            member_id=data.member_id,
            # The calendar day comes from the session, not from the moment the
            # box was ticked: every record of one evening has to count as the
            # same appointment, even one entered an hour later. Resolved in the
            # club's zone, so a session opening at 00:30 is filed under that
            # night rather than the previous UTC day.
            occurred_on=row.opens_at.astimezone(await self.club_timezone()).date(),
            checked_in_at=datetime.now(UTC),
            method=data.method,
            assurance=ASSURANCE_BY_METHOD[data.method],
            # Who vouches for it. For `manual` this is the whole proof of
            # person, which is why it is never optional.
            verified_by_user_id=self.auth.user_id,
            note=data.note,
            created_by=self.auth.user_id,
            updated_by=self.auth.user_id,
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get_record(self, record_id: uuid.UUID) -> AttendanceRecord:
        record = await self.records.get_by_id(record_id)
        if record is None:
            raise NotFoundError("Attendance record not found")
        return record

    async def require_record_exists(self, record_id: uuid.UUID) -> None:
        """Assert a record exists in this tenant, deleted or not.

        Used by the audit endpoint, which must keep answering after the record
        has been corrected away.
        """
        if not await self.records.exists_any_state(record_id):
            raise NotFoundError("Attendance record not found")

    async def require_session_exists(self, session_id: uuid.UUID) -> None:
        """Same, for sessions."""
        if not await self.sessions.exists_any_state(session_id):
            raise NotFoundError("Attendance session not found")

    async def check_out(self, record_id: uuid.UUID) -> AttendanceRecord:
        record = await self.get_record(record_id)
        await self._require_open(await self.get_session(record.session_id))
        if record.checked_out_at is not None:
            raise ConflictError("Member is already checked out")
        record.checked_out_at = datetime.now(UTC)
        record.updated_by = self.auth.user_id
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def update_record(
        self,
        record_id: uuid.UUID,
        data: AttendanceRecordUpdate,
        *,
        request: Request | None = None,
    ) -> AttendanceRecord:
        record = await self.get_record(record_id)
        await self._require_open(await self.get_session(record.session_id))

        changes = data.model_dump(exclude_unset=True, exclude={"reason"})
        before = {field: getattr(record, field) for field in changes}
        for field, value in changes.items():
            setattr(record, field, value)
        if record.checked_out_at is not None and record.checked_out_at < record.checked_in_at:
            raise ValidationError("checked_out_at must not be before checked_in_at")
        record.updated_by = self.auth.user_id
        await self.session.flush()

        applied = diff(before, changes)
        if applied:
            await record_tenant_action(
                self.session,
                self.auth,
                f"{RECORD_TARGET}.updated",
                target_type=RECORD_TARGET,
                target_id=record.id,
                request=request,
                changes=applied,
                reason=data.reason,
            )
        await self.session.refresh(record)
        return record

    async def delete_record(
        self, record_id: uuid.UUID, *, reason: str, request: Request | None = None
    ) -> None:
        """Soft-delete a record. The only removal path outside the retention job."""
        record = await self.get_record(record_id)
        await self._require_open(await self.get_session(record.session_id))

        # Who and when are kept in the entry: once the row is soft-deleted it
        # drops out of every ordinary query, and the trail has to stand alone.
        removed: dict[str, Any] = {
            "member_id": jsonable(record.member_id),
            "session_id": jsonable(record.session_id),
            "occurred_on": jsonable(record.occurred_on),
            "checked_in_at": jsonable(record.checked_in_at),
        }
        await self.records.soft_delete(record_id)
        await record_tenant_action(
            self.session,
            self.auth,
            f"{RECORD_TARGET}.deleted",
            target_type=RECORD_TARGET,
            target_id=record_id,
            request=request,
            changes=removed,
            reason=reason,
        )
