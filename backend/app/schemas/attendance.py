import uuid
from datetime import date, datetime
from typing import Any

from pydantic import Field, model_validator

from app.schemas.base import BaseSchema

# Only `manual` is built. The other methods exist in the model so assurance can
# be reasoned about as one scale; accepting them here would let a caller claim a
# level of proof no code path actually delivers.
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
    closed_at: datetime | None = None
    closed_by: uuid.UUID | None = None
    record_count: int = 0
    created_at: datetime
    updated_at: datetime


class AttendanceCheckIn(BaseSchema):
    member_id: uuid.UUID
    method: str = Field(default="manual", pattern=METHOD_PATTERN)
    note: str | None = Field(default=None, max_length=1000)

    # `checked_in_at` and `assurance` are deliberately not accepted. The time is
    # the server's, and the level of proof follows from the method — neither is
    # the caller's to assert.


class AttendanceRecordUpdate(BaseSchema):
    """A correction to the evidence layer. Always audited, always with a reason."""

    checked_out_at: datetime | None = None
    note: str | None = Field(default=None, max_length=1000)
    reason: str = Field(min_length=REASON_MIN_LENGTH, max_length=1000)


class AttendanceRecordResponse(BaseSchema):
    id: uuid.UUID
    session_id: uuid.UUID
    member_id: uuid.UUID
    member_name: str | None = None
    member_number: str | None = None
    occurred_on: date
    checked_in_at: datetime
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
