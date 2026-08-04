import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.dependencies import AuthContext
from app.models.attendance import (
    ASSURANCE_BY_METHOD,
    AttendanceCheckinContext,
    AttendanceRecord,
    AttendanceSession,
)
from app.models.member import Member
from app.models.tenant import Tenant
from app.redis import get_redis
from app.repositories.attendance import (
    AttendanceRecordRepository,
    AttendanceSessionRepository,
)
from app.repositories.member import MemberRepository
from app.schemas.attendance import (
    REASON_MIN_LENGTH,
    AttendanceCheckIn,
    AttendanceRecordUpdate,
    AttendanceScanCheckIn,
    AttendanceSeedResponse,
    AttendanceSessionCreate,
    AttendanceSessionUpdate,
)
from app.services.attendance_code import (
    CODE_INTERVAL_SECONDS,
    CODE_VERSION,
    REPLAY_TTL_SECONDS,
    InvalidCodeError,
    derive_seed,
    new_member_ref,
    parse_code,
    replay_key,
    seed_expires_at,
    seed_period,
    verify_code,
)
from app.services.audit import diff, jsonable, record_tenant_action
from app.services.proof_chain import append_entry, canonical_hash, session_close_hash

logger = structlog.get_logger()

SESSION_TARGET = "attendance_session"
RECORD_TARGET = "attendance_record"

# How far a device clock may run ahead of the server before its claim about
# when a check-in happened is refused. Generous enough for an unsynced phone,
# far short of letting anyone book into the future.
CLOCK_SKEW_ALLOWANCE = timedelta(minutes=5)

# One message for every way a code can fail. Which half of a guess was right is
# not something the endpoint should confirm.
INVALID_CODE_MESSAGE = "Code is not valid. Ask the member for a fresh one."


def action_for(action: str, amendment: dict[str, Any] | None) -> str:
    """Names a change made after the session was closed differently.

    So that reading the trail does not require comparing every entry's
    timestamp against the session's closing time to find out which changes were
    amendments.
    """
    return f"{action}_after_close" if amendment is not None else action


def _context_digest(context: AttendanceCheckinContext) -> str:
    """Fingerprint of the context row, canonical and order-independent.

    Written to the record so the context stays *attestable* after the row
    itself has been deleted by the retention job.
    """
    canonical = "|".join(
        f"{field}={getattr(context, field) or ''}"
        for field in ("install_id", "staff_device_id", "code_counter")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


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

    def _amendment(self, row: AttendanceSession, reason: str | None) -> dict[str, Any] | None:
        """Guards and describes a change made after a session was closed.

        Closing used to make a record untouchable, and that freeze is what
        assurance level 0 rested on: a late entry was impossible rather than
        merely visible. Corrections after the fact are now allowed for the
        board, which is a deliberate trade of that property for the ability to
        fix a real mistake found the next day.

        What keeps it defensible is that such a change cannot be quiet. A reason
        is mandatory, the audit action is a different one, and the entry carries
        when the session was closed — so anyone reading the trail can separate
        what happened during the evening from what happened afterwards without
        having to compare timestamps by hand.

        Returns null while the session is open, meaning "nothing to declare".
        """
        if row.status != "closed":
            return None
        if reason is None or len(reason.strip()) < REASON_MIN_LENGTH:
            raise ValidationError(
                "A closed session can only be changed with a reason of at least "
                f"{REASON_MIN_LENGTH} characters."
            )
        return {
            "session_closed_at": jsonable(row.closed_at),
            "session_closed_by": jsonable(row.closed_by),
        }

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

        # Assurance level 1: hash the final record list and chain it. The
        # close_hash means "this was the state at closing" — since amendments
        # became possible it can no longer mean "nothing happened after", which
        # is exactly why an amendment appends its own link instead of touching
        # this one.
        live_records = [r for r, *_ in await self.records.get_for_session(session_id)]
        row.close_hash = session_close_hash(session_id, live_records)
        await self.session.flush()
        await append_entry(
            self.session,
            self.tenant_id,
            entry_type="session_close",
            subject_id=row.id,
            content_hash=row.close_hash,
        )

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

        if data.member_id is not None and await self.members.get_by_id(data.member_id) is None:
            raise NotFoundError("Member not found")

        return await self._record_check_in(
            row,
            record_id=data.id,
            member_id=data.member_id,
            guest_name=data.guest_name,
            method=data.method,
            note=data.note,
            claimed_at=data.checked_in_at,
        )

    def _resolve_occurred_at(
        self, row: AttendanceSession, claimed_at: datetime | None
    ) -> tuple[datetime, datetime | None]:
        """Settle when the check-in happened, and whether it arrived late.

        Without a claim the server's clock is both: it was happening as we were
        told. With one, the claim becomes `checked_in_at` and now becomes
        `synced_at`, so the record carries both facts and an audit can tell a
        live check-in from a drained queue.

        The claim is bounded rather than trusted. A device could otherwise
        backdate someone into an evening they were not at, which is precisely
        the attack the freeze on closed sessions exists to prevent — a buffered
        write must not become a way around it.
        """
        now = datetime.now(UTC)
        if claimed_at is None:
            return now, None

        claimed = claimed_at.astimezone(UTC)
        if claimed > now + CLOCK_SKEW_ALLOWANCE:
            raise ValidationError("checked_in_at is in the future")
        if claimed < row.opens_at:
            raise ValidationError("checked_in_at is before the session opened")
        return claimed, now

    async def _record_check_in(
        self,
        row: AttendanceSession,
        *,
        record_id: uuid.UUID | None = None,
        member_id: uuid.UUID | None = None,
        guest_name: str | None = None,
        method: str,
        note: str | None,
        claimed_at: datetime | None = None,
    ) -> AttendanceRecord:
        """The shared half of every check-in, whatever proved the person.

        A client-assigned [record_id] makes the whole call idempotent, checked
        *before* the member-dedupe below: a replayed request is a retry, and a
        retry answering `ALREADY_CHECKED_IN` would dress the queue's own
        success up as somebody else's conflict.
        """
        if record_id is not None:
            replayed = await self.records.get_by_id(record_id)
            if replayed is not None:
                return replayed

        occurred_at, synced_at = self._resolve_occurred_at(row, claimed_at)

        # Guests are not deduplicated: nothing about a guest identifies them
        # well enough to tell a second visitor of the same name from the same
        # person twice, and refusing the second one would lose a real
        # attendance to guard against a bookkeeping annoyance.
        if member_id is not None and await self.records.get_active(row.id, member_id) is not None:
            # Its own code: for a supervisor scanning a queue this is a
            # non-event, while a used code means someone passed a screenshot
            # around. The two must not read the same on screen.
            raise ConflictError(
                "Member is already checked in for this session", code="ALREADY_CHECKED_IN"
            )

        record = AttendanceRecord(
            id=record_id or uuid.uuid4(),
            tenant_id=self.tenant_id,
            session_id=row.id,
            member_id=member_id,
            guest_name=guest_name,
            # The calendar day comes from the session, not from the moment the
            # box was ticked: every record of one evening has to count as the
            # same appointment, even one entered an hour later. Resolved in the
            # club's zone, so a session opening at 00:30 is filed under that
            # night rather than the previous UTC day.
            occurred_on=row.opens_at.astimezone(await self.club_timezone()).date(),
            checked_in_at=occurred_at,
            synced_at=synced_at,
            method=method,
            assurance=ASSURANCE_BY_METHOD[method],
            # Who vouches for it. For `manual` this is the whole proof of
            # person; for `staff_scan` it is who operated the scanner. Never
            # optional either way.
            verified_by_user_id=self.auth.user_id,
            note=note,
            created_by=self.auth.user_id,
            updated_by=self.auth.user_id,
        )
        # A savepoint, not the request transaction — the pattern from
        # `EntryRepository.create_idempotent`: two racing drains with the same
        # client key must resolve to one row, and a plain rollback would take
        # the request's other uncommitted work down with the duplicate.
        try:
            async with self.session.begin_nested():
                self.session.add(record)
                await self.session.flush()
        except IntegrityError:
            if record_id is not None:
                replayed = await self.records.get_by_id(record_id)
                if replayed is not None:
                    return replayed
            raise
        await self.session.refresh(record)
        return record

    # --- Rotating code ---

    async def member_seed(self, member: Member) -> AttendanceSeedResponse:
        """Hand a member the seed their app computes codes from.

        Mints the pseudonym on first use. Doing it here rather than at member
        creation keeps the column empty for the clubs that never scan, and means
        an existing database needs no backfill.
        """
        if member.attendance_ref is None:
            member.attendance_ref = new_member_ref()
            await self.session.flush()

        settings = get_settings()
        period = seed_period(int(datetime.now(UTC).timestamp()))
        return AttendanceSeedResponse(
            member_ref=member.attendance_ref,
            seed=derive_seed(settings.ATTENDANCE_SECRET, self.tenant_id, member.id, period),
            tenant_id=self.tenant_id,
            expires_at=seed_expires_at(period),
            interval_seconds=CODE_INTERVAL_SECONDS,
            algorithm=CODE_VERSION,
        )

    async def check_in_by_code(
        self, session_id: uuid.UUID, data: AttendanceScanCheckIn
    ) -> AttendanceRecord:
        """Check a member in from their rotating code.

        The order matters. Structure, then identity, then signature, then
        single-use — each step is cheap relative to the next, and the burn only
        happens once the code is known to be genuine, so a garbled scan cannot
        consume a window the member still needs.
        """
        row = await self.get_session(session_id)
        await self._require_open(row)

        try:
            parsed = parse_code(data.code)
        except InvalidCodeError as exc:
            # A camera reads whatever is in front of it, so garbage arriving
            # here is routine input, not an exceptional condition.
            raise ValidationError(INVALID_CODE_MESSAGE) from exc

        member = await self.members.get_by_attendance_ref(parsed.member_ref)
        if member is None:
            # Deliberately the same error as a bad signature: distinguishing
            # "no such member" from "wrong code" turns the endpoint into an
            # oracle for which pseudonyms exist.
            raise ValidationError(INVALID_CODE_MESSAGE)

        # A buffered scan is checked against the moment it claims to have
        # happened, not against now — a code read twenty minutes ago in a
        # basement is long stale by the server's clock, and refusing it would
        # make offline scanning impossible. The claim is bounded by the session
        # window in `_resolve_occurred_at`, and the MAC still proves the
        # member's own device produced this code for that counter. What is lost
        # is the server's independent word on *when*, which is exactly why
        # `synced_at` is stored beside it.
        occurred_at, _ = self._resolve_occurred_at(row, data.checked_in_at)

        settings = get_settings()
        try:
            verify_code(
                parsed,
                secret=settings.ATTENDANCE_SECRET,
                tenant_id=self.tenant_id,
                member_id=member.id,
                now=int(occurred_at.timestamp()),
            )
        except InvalidCodeError as exc:
            raise ValidationError(INVALID_CODE_MESSAGE) from exc

        await self._burn_code(member.id, parsed.counter)

        record = await self._record_check_in(
            row,
            member_id=member.id,
            method="staff_scan",
            note=data.note,
            claimed_at=data.checked_in_at,
        )
        await self._record_context(record, parsed.counter, data)
        return record

    async def _burn_code(self, member_id: uuid.UUID, counter: int) -> None:
        """Make a code single-use. This is what kills screenshot replay.

        `nx=True` is the whole mechanism: the first caller sets the key, every
        later one finds it there. Redis being unavailable fails the check-in
        rather than waving it through — a check-in that cannot be guaranteed
        unique is worth less than no check-in at all, given the point is proof.
        """
        key = replay_key(self.tenant_id, member_id, counter)
        if not await get_redis().set(key, "1", nx=True, ex=REPLAY_TTL_SECONDS):
            raise ConflictError(
                "This code has already been used. Ask for a fresh one.", code="CODE_ALREADY_USED"
            )

    async def _record_context(
        self, record: AttendanceRecord, counter: int, data: AttendanceScanCheckIn
    ) -> None:
        """Write the short-lived technical context and its lasting fingerprint.

        The digest goes on the record, which outlives the context by years. Once
        the context row is gone, what stays provable is "a technical context
        with this fingerprint existed for this check-in and was unremarkable" —
        the statement that is actually needed in a dispute, without keeping the
        behavioural trail around to make it.
        """
        tenant = await self.session.get(Tenant, self.tenant_id)
        retention_days = tenant.attendance_context_retention_days if tenant else 90

        context = AttendanceCheckinContext(
            tenant_id=self.tenant_id,
            attendance_record_id=record.id,
            install_id=data.install_id,
            staff_device_id=data.staff_device_id,
            code_counter=counter,
            expires_at=datetime.now(UTC) + timedelta(days=retention_days),
        )
        self.session.add(context)

        record.context_digest = _context_digest(context)
        # No abuse detection yet — saying "ok" would be a claim nothing checked.
        record.context_verdict = "unchecked"
        await self.session.flush()

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
        session_row = await self.get_session(record.session_id)
        amendment = self._amendment(session_row, data.reason)

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
                action_for(f"{RECORD_TARGET}.updated", amendment),
                target_type=RECORD_TARGET,
                target_id=record.id,
                request=request,
                changes=applied | (amendment or {}),
                reason=data.reason,
            )
            if amendment is not None:
                await self._chain_amendment(
                    record, session_row, action="updated", changes=applied, reason=data.reason
                )
        await self.session.refresh(record)
        return record

    async def _chain_amendment(
        self,
        record: AttendanceRecord,
        session_row: AttendanceSession,
        *,
        action: str,
        changes: dict[str, Any],
        reason: str | None,
    ) -> None:
        """Chain a correction made after the session was closed.

        Its own link rather than a rewrite of the close link — the close_hash
        stays what it was ("the state at closing"), and the amendment commits
        to it, so the chain reads: closed at X, amended against X.
        """
        await append_entry(
            self.session,
            self.tenant_id,
            entry_type="record_amendment",
            subject_id=record.id,
            content_hash=canonical_hash(
                {
                    "record_id": str(record.id),
                    "session_id": str(session_row.id),
                    "session_close_hash": session_row.close_hash,
                    "action": action,
                    "changes": changes,
                    "reason": reason,
                    "actor_user_id": str(self.auth.user_id),
                }
            ),
        )

    async def delete_record(
        self, record_id: uuid.UUID, *, reason: str | None = None, request: Request | None = None
    ) -> None:
        """Soft-delete a record. The only removal path outside the retention job.

        Inside an open session the reason may be omitted: a removal there is
        almost always a mistap from seconds ago, and the audit entry's actor and
        timestamp are what evidence it. Once the session is closed a reason
        becomes mandatory and the entry is filed under a different action — see
        [_amendment].
        """
        record = await self.get_record(record_id)
        session_row = await self.get_session(record.session_id)
        amendment = self._amendment(session_row, reason)

        # Who and when are kept in the entry: once the row is soft-deleted it
        # drops out of every ordinary query, and the trail has to stand alone.
        removed: dict[str, Any] = {
            "member_id": jsonable(record.member_id),
            "session_id": jsonable(record.session_id),
            "occurred_on": jsonable(record.occurred_on),
            "checked_in_at": jsonable(record.checked_in_at),
        } | (amendment or {})
        await self.records.soft_delete(record_id)
        await record_tenant_action(
            self.session,
            self.auth,
            action_for(f"{RECORD_TARGET}.deleted", amendment),
            target_type=RECORD_TARGET,
            target_id=record_id,
            request=request,
            changes=removed,
            reason=reason,
        )
        if amendment is not None:
            await self._chain_amendment(
                record, session_row, action="deleted", changes=removed, reason=reason
            )
