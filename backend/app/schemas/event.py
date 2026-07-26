import uuid
from datetime import datetime

from pydantic import Field, model_validator

from app.schemas.base import BaseSchema

EVENT_TYPE_PATTERN = "^(training|meeting|celebration|competition|other)$"


class EventCreate(BaseSchema):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    event_type: str = Field(default="other", pattern=EVENT_TYPE_PATTERN)
    location: str | None = Field(default=None, max_length=255)
    starts_at: datetime
    ends_at: datetime | None = None
    all_day: bool = False
    registration_required: bool = False
    registration_deadline: datetime | None = None
    max_participants: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_times(self) -> "EventCreate":
        if self.ends_at is not None and self.ends_at < self.starts_at:
            raise ValueError("ends_at must not be before starts_at")
        return self


class EventUpdate(BaseSchema):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    event_type: str | None = Field(default=None, pattern=EVENT_TYPE_PATTERN)
    location: str | None = Field(default=None, max_length=255)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    all_day: bool | None = None
    registration_required: bool | None = None
    registration_deadline: datetime | None = None
    max_participants: int | None = Field(default=None, ge=1)
    status: str | None = Field(default=None, pattern="^(scheduled|cancelled)$")


class EventResponse(BaseSchema):
    id: uuid.UUID
    title: str
    description: str | None = None
    event_type: str
    location: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    all_day: bool
    registration_required: bool
    registration_deadline: datetime | None = None
    max_participants: int | None = None
    status: str
    registered_count: int = 0
    created_at: datetime
    updated_at: datetime


class EventRegistrationCreate(BaseSchema):
    member_id: uuid.UUID
    note: str | None = Field(default=None, max_length=5000)


class EventRegistrationResponse(BaseSchema):
    id: uuid.UUID
    event_id: uuid.UUID
    member_id: uuid.UUID
    member_name: str | None = None
    status: str
    note: str | None = None
    created_at: datetime
