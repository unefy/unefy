import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from pydantic import Field, field_validator

from app.schemas.base import BaseSchema

#: `free_training` is the auto-created container for shots recorded without a
#: competition — a member on the range by themselves. Kept out of competition
#: lists by default so it does not clutter them; see `app/api/v1/competitions.py`.
VALID_TYPES = {"league", "competition", "training", "free_training"}
FREE_TRAINING_TYPE = "free_training"
VALID_SCORING_MODES = {"highest_wins", "lowest_wins"}
VALID_SOURCES = {"manual", "scan"}


# --- Shot detail (shooting) ---


class ShotDetail(BaseSchema):
    """One shot on a target.

    Coordinates are normalised to the RING 1 RADIUS with the origin at the
    target centre and y pointing down, so (0, 0) is dead centre and a magnitude
    of 1.0 sits on the outer edge of ring 1. The bounds allow a little beyond
    that: a miss still has a position worth keeping.
    """

    x: float = Field(ge=-1.5, le=1.5)
    y: float = Field(ge=-1.5, le=1.5)
    ring: int = Field(ge=0, le=10)  # 0 = miss
    inner_ten: bool = False
    #: Caliber of this individual shot, when it differs from the series. Set
    #: only in the mixed case; normally the series-level value applies.
    caliber_mm: float | None = Field(default=None, gt=0, le=30)
    source: str = Field(default="manual", max_length=20)

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in VALID_SOURCES:
            raise ValueError(f"Must be one of {VALID_SOURCES}")
        return v


class EntryDetails(BaseSchema):
    """The shooting payload stored in `Entry.details`.

    Written by the server after it has recomputed every ring, so the ring values
    here are authoritative even when the client sent different ones.
    """

    shots: list[ShotDetail] = Field(max_length=200)
    target_type: str = Field(max_length=100)
    #: Caliber used for the series, in mm. The default for every shot that does
    #: not carry its own.
    caliber_mm: float | None = Field(default=None, gt=0, le=30)
    inner_tens: int | None = None
    grouping_mm: float | None = None


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
    # Optionally create a linked calendar event for this session.
    create_calendar_event: bool = False
    starts_at: dt.datetime | None = None


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
    event_id: uuid.UUID | None = None
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


# --- Shot entry (the recording endpoint) ---


class ShotPosition(BaseSchema):
    """A shot as the client places it. The ring is computed server-side."""

    x: float = Field(ge=-1.5, le=1.5)
    y: float = Field(ge=-1.5, le=1.5)
    caliber_mm: float | None = Field(default=None, gt=0, le=30)
    #: What the client scored it as. Not trusted — recorded only so a
    #: disagreement between the two scoring engines can be logged.
    ring: int | None = Field(default=None, ge=0, le=10)
    #: Per shot, because one series mixes the two: the photo detector proposes
    #: shots ("scan") and the shooter corrects them ("manual"). Keeping the
    #: distinction is what lets the detector be measured against what actually
    #: happened, on real sheets, without anybody annotating anything twice.
    source: str | None = Field(default=None, max_length=20)

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_SOURCES:
            raise ValueError(f"Must be one of {VALID_SOURCES}")
        return v


class ShotEntryUpdate(BaseSchema):
    """Correct a series that was already recorded.

    Only the shots and what scores them: the member, the day and the session it
    belongs to are not editable here — moving a result to another member or
    another competition is a different act, and it should look different.
    """

    shots: list[ShotPosition] = Field(max_length=200)
    target_type: str | None = Field(default=None, min_length=1, max_length=100)
    caliber_mm: float | None = Field(default=None, gt=0, le=30)
    notes: str | None = Field(default=None, max_length=5000)


class ShotEntryCreate(BaseSchema):
    """Record one series of shots.

    Covers both cases with one shape: pass `session_id` to file the series under
    a competition or training session, or leave it out and pass `occurred_on` to
    have it filed under the club's automatic "Freies Training" series.

    `id` is client-generated so an offline queue can retry without creating
    duplicates.
    """

    id: uuid.UUID | None = None
    member_id: uuid.UUID
    session_id: uuid.UUID | None = None
    occurred_on: dt.date | None = None
    discipline: str | None = Field(default=None, max_length=100)
    target_type: str = Field(min_length=1, max_length=100)
    caliber_mm: float | None = Field(default=None, gt=0, le=30)
    shots: list[ShotPosition] = Field(max_length=200)
    source: str = Field(default="manual", max_length=20)
    recorded_at: dt.datetime
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in VALID_SOURCES:
            raise ValueError(f"Must be one of {VALID_SOURCES}")
        return v


# --- Scoreboard ---


class ScoreboardRow(BaseSchema):
    """One ranked line. Kept in step with what the scoreboard route actually
    assembles — the route builds dicts, and this schema is the contract the
    mobile DTOs are validated against, so a field the route adds belongs here.
    """

    rank: int
    member_id: uuid.UUID
    member_name: str
    total_score: float
    entry_count: int
    average_score: float
    best_score: float
