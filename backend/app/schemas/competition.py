import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from pydantic import Field, field_validator

from app.schemas.base import BaseSchema

VALID_TYPES = {"league", "competition", "training"}
VALID_SCORING_MODES = {"highest_wins", "lowest_wins"}
VALID_SOURCES = {"manual", "scan"}


# --- Competition ---


class CompetitionCreate(BaseSchema):
    id: uuid.UUID | None = None  # Client-generated UUID for offline sync.
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    competition_type: str = Field(default="competition", max_length=50)
    start_date: dt.date
    end_date: dt.date | None = None
    scoring_mode: str = Field(default="highest_wins", max_length=20)
    scoring_unit: str = Field(default="Punkte", max_length=50)
    disciplines: list[str] | None = None

    @field_validator("competition_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_TYPES:
            raise ValueError(f"Must be one of {VALID_TYPES}")
        return v

    @field_validator("scoring_mode")
    @classmethod
    def validate_scoring_mode(cls, v: str) -> str:
        if v not in VALID_SCORING_MODES:
            raise ValueError(f"Must be one of {VALID_SCORING_MODES}")
        return v


class CompetitionUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    competition_type: str | None = Field(default=None, max_length=50)
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    scoring_mode: str | None = Field(default=None, max_length=20)
    scoring_unit: str | None = Field(default=None, max_length=50)
    disciplines: list[str] | None = None

    @field_validator("competition_type")
    @classmethod
    def validate_type(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_TYPES:
            raise ValueError(f"Must be one of {VALID_TYPES}")
        return v

    @field_validator("scoring_mode")
    @classmethod
    def validate_scoring_mode(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_SCORING_MODES:
            raise ValueError(f"Must be one of {VALID_SCORING_MODES}")
        return v


class CompetitionResponse(BaseSchema):
    id: uuid.UUID
    name: str
    description: str | None
    competition_type: str
    start_date: dt.date
    end_date: dt.date | None
    scoring_mode: str
    scoring_unit: str
    disciplines: list[str] | None
    created_at: dt.datetime
    updated_at: dt.datetime


# --- Session ---


class SessionCreate(BaseSchema):
    id: uuid.UUID | None = None  # Client-generated UUID for offline sync.
    name: str | None = Field(default=None, max_length=255)
    date: dt.date
    location: str | None = Field(default=None, max_length=255)
    discipline: str | None = Field(default=None, max_length=100)


class SessionUpdate(BaseSchema):
    name: str | None = Field(default=None, max_length=255)
    date: dt.date | None = None
    location: str | None = Field(default=None, max_length=255)
    discipline: str | None = Field(default=None, max_length=100)


class SessionResponse(BaseSchema):
    id: uuid.UUID
    competition_id: uuid.UUID
    name: str | None
    date: dt.date
    location: str | None
    discipline: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


# --- Entry ---


class EntryCreate(BaseSchema):
    """Create a scoring entry. `id` is optional — clients send their own
    UUID for idempotent offline sync."""

    id: uuid.UUID | None = None
    member_id: uuid.UUID
    score_value: Decimal = Field(ge=0)
    score_unit: str = Field(default="Punkte", max_length=50)
    discipline: str | None = Field(default=None, max_length=100)
    details: dict[str, Any] | None = None
    source: str = Field(default="manual", max_length=20)
    recorded_at: dt.datetime
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in VALID_SOURCES:
            raise ValueError(f"Must be one of {VALID_SOURCES}")
        return v


class EntryUpdate(BaseSchema):
    score_value: Decimal | None = Field(default=None, ge=0)
    details: dict[str, Any] | None = None
    notes: str | None = Field(default=None, max_length=5000)


class EntryResponse(BaseSchema):
    id: uuid.UUID
    session_id: uuid.UUID
    member_id: uuid.UUID
    score_value: float  # Decimal → float for JSON (iOS expects number, not string)
    score_unit: str
    discipline: str | None
    details: dict[str, Any] | None
    source: str
    recorded_by: uuid.UUID | None
    recorded_at: dt.datetime
    notes: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


# --- Scoreboard ---


class ScoreboardRow(BaseSchema):
    member_id: uuid.UUID
    total_score: float
    entry_count: int
    average_score: float
    best_score: float
