import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema

INTERVAL_PATTERN = "^(yearly|half_yearly|quarterly|monthly|one_time)$"


# --- FeeType ---


class FeeTypeCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    amount: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    interval: str = Field(default="yearly", pattern=INTERVAL_PATTERN)
    is_active: bool = True


class FeeTypeUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    interval: str | None = Field(default=None, pattern=INTERVAL_PATTERN)
    is_active: bool | None = None


class FeeTypeResponse(BaseSchema):
    id: uuid.UUID
    name: str
    description: str | None = None
    amount: Decimal
    interval: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --- MemberFee (assignment) ---


class MemberFeeCreate(BaseSchema):
    member_id: uuid.UUID
    fee_type_id: uuid.UUID
    valid_from: date
    valid_to: date | None = None
    note: str | None = Field(default=None, max_length=5000)


class MemberFeeUpdate(BaseSchema):
    valid_from: date | None = None
    valid_to: date | None = None
    note: str | None = Field(default=None, max_length=5000)


class MemberFeeResponse(BaseSchema):
    id: uuid.UUID
    member_id: uuid.UUID
    fee_type_id: uuid.UUID
    valid_from: date
    valid_to: date | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Due ---


class DueGenerateRequest(BaseSchema):
    year: int = Field(ge=2000, le=2100)


class DuePayRequest(BaseSchema):
    paid_at: date | None = None  # defaults to today in service
    payment_method: str | None = Field(default=None, max_length=50)
    note: str | None = Field(default=None, max_length=5000)


class DueUpdate(BaseSchema):
    note: str | None = Field(default=None, max_length=5000)
    due_date: date | None = None


class DueResponse(BaseSchema):
    id: uuid.UUID
    member_id: uuid.UUID
    member_name: str | None = None
    fee_type_id: uuid.UUID
    fee_name: str
    amount: Decimal
    period_start: date
    period_end: date
    due_date: date
    status: str
    paid_at: date | None = None
    payment_method: str | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class DueSummaryResponse(BaseSchema):
    open_count: int
    open_amount: Decimal
    paid_count: int
    paid_amount: Decimal
