import uuid
from datetime import date, datetime
from typing import Any

from pydantic import Field, model_validator

from app.schemas.base import BaseSchema

# `manual` and `staff_scan` are built. The remaining methods exist in the model
# so assurance can be reasoned about as one scale; accepting them here would let
# a caller claim a level of proof no code path actually delivers.
METHOD_PATTERN = "^(manual)$"

# Corrections to the evidence layer must carry a human reason — that is what
# assurance level 0 buys. Short enough not to be a burden, long enough that
# "x" does not pass for one.
REASON_MIN_LENGTH = 3


class AttendanceSessionCreate(BaseSchema):
    title: str = Field(min_length=1, max_length=255)
    division_id: uuid.UUID | None = None
    event_id: uuid.UUID | None = None
    location: str | None = Field(default=None, max_length=255)
    opens_at: datetime
    closes_at: datetime
    supervisor_member_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_window(self) -> "AttendanceSessionCreate":
        if self.closes_at <= self.opens_at:
            raise ValueError("closes_at must be after opens_at")
        return self


class AttendanceSessionUpdate(BaseSchema):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    division_id: uuid.UUID | None = None
    event_id: uuid.UUID | None = None
    location: str | None = Field(default=None, max_length=255)
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    supervisor_member_id: uuid.UUID | None = None
    reason: str | None = Field(default=None, max_length=1000)

    # `status` is deliberately absent: closing is its own endpoint, because it
    # freezes the session and must not happen as a side effect of an edit.


class AttendanceSessionResponse(BaseSchema):
    id: uuid.UUID
    title: str
    division_id: uuid.UUID | None = None
    event_id: uuid.UUID | None = None
    location: str | None = None
    opens_at: datetime
    closes_at: datetime
    status: str
    supervisor_member_id: uuid.UUID | None = None
    supervisor_name: str | None = None
    event_title: str | None = None
    closed_at: datetime | None = None
    closed_by: uuid.UUID | None = None
    record_count: int = 0
    created_at: datetime
    updated_at: datetime


class BufferedCheckIn(BaseSchema):
    """Shared by both check-in paths: the one thing a queued write may assert.

    `checked_in_at` is the device's clock, and it is accepted *only* because a
    buffered check-in has no other source for when it happened — the server's
    clock says when the queue drained, which is a different fact and is stored
    separately as `synced_at`. It is a claim, not evidence, so the service
    bounds it by the session's own window and by now.

    `assurance` stays unacceptable. The level of proof follows from the method,
    and no client gets to name it.
    """

    checked_in_at: datetime | None = None


class AttendanceCheckIn(BufferedCheckIn):
    """A member or a guest, never both.

    Mirrors the database's CHECK rather than trusting it: a caller that sends
    neither gets a readable error here instead of an integrity violation, and
    one that sends both is told which rule it broke.
    """

    #: Client-assigned, optional. The whole point is the offline queue: a drain
    #: that is interrupted and retried must not book the same guest twice, and
    #: nothing about a guest identifies them well enough to deduplicate by
    #: content. The key distinguishes *a retry* from *two real guests* without
    #: pretending to identify anyone. Absent, the server assigns one — exactly
    #: today's behaviour.
    id: uuid.UUID | None = None

    member_id: uuid.UUID | None = None
    guest_name: str | None = Field(default=None, min_length=1, max_length=255)
    method: str = Field(default="manual", pattern=METHOD_PATTERN)
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_subject(self) -> "AttendanceCheckIn":
        if (self.member_id is None) == (self.guest_name is None):
            raise ValueError("Provide exactly one of member_id or guest_name")
        return self


class AttendanceScanCheckIn(BufferedCheckIn):
    """A supervisor scanning a member's rotating code.

    A separate schema rather than an optional `code` on [AttendanceCheckIn]:
    the two carry different proof. Here the member is not named at all — they
    are derived from the code, which is the entire reason this method rates
    `high` while a ticked box rates `low`. Letting one schema express both would
    let a caller send a member id *and* a code and leave the question of which
    one wins to the implementation.
    """

    code: str = Field(min_length=1, max_length=128)
    note: str | None = Field(default=None, max_length=1000)

    # Context of the scan, all optional — the check-in must not fail because a
    # scanner withheld its identity. Retained on the short clock.
    install_id: str | None = Field(default=None, max_length=64)
    staff_device_id: str | None = Field(default=None, max_length=64)


class AttendanceSeedResponse(BaseSchema):
    """What a member's app needs to compute its own codes offline."""

    member_ref: str
    seed: str
    # The MAC is taken over the tenant as well, so the app needs it. Returned
    # here rather than read from the session: this response is then the single
    # authoritative statement of every input the code is built from, and the
    # two cannot drift apart.
    tenant_id: uuid.UUID
    # Unix seconds. The app refreshes against this; a late refresh is not a
    # lockout, because the verifier accepts a couple of expired periods.
    expires_at: int
    interval_seconds: int
    algorithm: str


class AttendanceRecordUpdate(BaseSchema):
    """A correction to the evidence layer. Always audited, always with a reason."""

    checked_out_at: datetime | None = None
    note: str | None = Field(default=None, max_length=1000)
    reason: str = Field(min_length=REASON_MIN_LENGTH, max_length=1000)


class SelfEntryCreate(BaseSchema):
    """A member's own entry about a visit to some other range.

    Only the claim itself: which day, which range. Method and assurance are
    derived server-side, like everywhere else — a self-entry that could name
    its own credibility would not have any.
    """

    occurred_on: date
    location: str = Field(min_length=1, max_length=255)
    note: str | None = Field(default=None, max_length=1000)


class AttendanceRecordResponse(BaseSchema):
    id: uuid.UUID
    # Null for an external self-entry, which has no session to hang off.
    session_id: uuid.UUID | None = None
    origin: str = "club"
    external_location: str | None = None
    # Null for a guest, who is named by `guest_name` instead.
    member_id: uuid.UUID | None = None
    guest_name: str | None = None
    member_name: str | None = None
    member_number: str | None = None
    occurred_on: date
    checked_in_at: datetime
    # Non-null means the check-in was buffered on a device and arrived later —
    # visible in the record so an audit can tell the two apart.
    synced_at: datetime | None = None
    checked_out_at: datetime | None = None
    method: str
    assurance: str
    verified_by_user_id: uuid.UUID | None = None
    note: str | None = None
    created_at: datetime


class MemberAttendanceRecordResponse(AttendanceRecordResponse):
    """A record seen from the member's side — the session is the context."""

    session_title: str | None = None
    session_location: str | None = None


class AuditEntryResponse(BaseSchema):
    id: uuid.UUID
    action: str
    target_type: str
    target_id: uuid.UUID
    actor_user_id: uuid.UUID | None = None
    # Resolved for display: a trail that shows a user id is unreadable.
    actor_name: str | None = None
    changes: dict[str, Any] | None = None
    reason: str | None = None
    created_at: datetime
