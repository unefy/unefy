import uuid
from datetime import date, datetime

from pydantic import Field, model_validator

from app.schemas.base import BaseSchema

WEAPON_CATEGORY_PATTERN = "^(kurzwaffe|langwaffe|luftdruck)$"

# Same bar as attendance corrections: revoking an issued proof is a statement
# about evidence and has to say why.
REASON_MIN_LENGTH = 3


class ShootingRecordDetailUpdate(BaseSchema):
    """What was shot at one attendance. Upserted — the first PATCH creates."""

    club_discipline_id: uuid.UUID | None = None
    weapon_category: str | None = Field(default=None, pattern=WEAPON_CATEGORY_PATTERN)
    rounds_fired: int | None = Field(default=None, ge=0, le=100_000)


class ShootingRecordDetailResponse(BaseSchema):
    id: uuid.UUID
    attendance_record_id: uuid.UUID
    club_discipline_id: uuid.UUID | None = None
    weapon_category: str | None = None
    rounds_fired: int | None = None


class ShootingProofRuleCreate(BaseSchema):
    rule_key: str = Field(min_length=1, max_length=50, pattern="^[a-z0-9_-]+$")
    label: str = Field(min_length=1, max_length=255)
    window_months: int = Field(default=12, ge=1, le=60)
    min_total_days: int | None = Field(default=None, ge=1, le=1000)
    min_distinct_months: int | None = Field(default=None, ge=1, le=60)

    @model_validator(mode="after")
    def validate_criteria(self) -> "ShootingProofRuleCreate":
        if self.min_total_days is None and self.min_distinct_months is None:
            raise ValueError("A rule needs at least one criterion")
        return self


class ShootingProofRuleUpdate(BaseSchema):
    label: str | None = Field(default=None, min_length=1, max_length=255)
    window_months: int | None = Field(default=None, ge=1, le=60)
    min_total_days: int | None = Field(default=None, ge=1, le=1000)
    min_distinct_months: int | None = Field(default=None, ge=1, le=60)
    # `rule_key` is deliberately not editable: issued certificates carry it,
    # and renaming the key would orphan their reference to what was tested.


class ShootingProofRuleResponse(BaseSchema):
    id: uuid.UUID
    rule_key: str
    label: str
    window_months: int
    min_total_days: int | None = None
    min_distinct_months: int | None = None
    created_at: datetime
    updated_at: datetime


class ProofEvaluationResponse(BaseSchema):
    """The live evaluation — a proposal, never a certificate."""

    member_id: uuid.UUID
    rule_key: str
    period_start: date
    period_end: date
    session_count: int
    months_covered: int
    passed: bool


class CertificateIssue(BaseSchema):
    member_id: uuid.UUID
    rule_key: str = Field(min_length=1, max_length=50)
    # The reference day the window counts back from; defaults to today in the
    # club's time zone. Named so a proof for "as of the application date" can
    # be issued a few days later without lying.
    as_of: date | None = None


class CertificateRevoke(BaseSchema):
    reason: str = Field(min_length=REASON_MIN_LENGTH, max_length=1000)


class CertificateResponse(BaseSchema):
    id: uuid.UUID
    member_id: uuid.UUID
    member_name: str | None = None
    rule_key: str
    period_start: date
    period_end: date
    session_count: int
    months_covered: int
    result: str
    issued_at: datetime
    issued_by_user_id: uuid.UUID
    revoked_at: datetime | None = None
    revoke_reason: str | None = None
    content_hash: str
    verification_code: str
