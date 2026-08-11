import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, model_validator

from app.models.donation import DONATION_KINDS
from app.schemas.base import BaseSchema

KIND_PATTERN = f"^({'|'.join(DONATION_KINDS)})$"


class ReceiptCreate(BaseSchema):
    """One donation, as the club records it.

    Either a member — then the name and address come from the register — or a
    typed-in donor. A receipt whose name differs from the register by a typo
    is a receipt somebody has to explain.
    """

    member_id: uuid.UUID | None = None
    donor_name: str | None = Field(default=None, max_length=255)
    donor_address: str | None = Field(default=None, max_length=500)

    #: Two decimals, positive. `Decimal` rather than float all the way down —
    #: money that rounds on the way to a tax office is not money.
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    received_on: date
    kind: str = Field(pattern=KIND_PATTERN)
    #: A waiver of reimbursement of expenses. The form asks explicitly, so the
    #: answer belongs on the paper either way.
    is_expense_waiver: bool = False

    @model_validator(mode="after")
    def validate_donor(self) -> "ReceiptCreate":
        if self.member_id is None and not (self.donor_name or "").strip():
            raise ValueError("Either a member or a donor name is required")
        return self


class RevokeRequest(BaseSchema):
    reason: str = Field(min_length=1, max_length=1000)


class ReceiptResponse(BaseSchema):
    id: uuid.UUID
    member_id: uuid.UUID | None = None
    donor_name: str
    donor_address: str | None = None
    amount: Decimal
    received_on: date
    kind: str
    is_expense_waiver: bool
    club_name: str
    exemption_kind: str
    exemption_date: date
    exemption_period: int | None = None
    tax_office: str
    tax_number: str
    purposes: str
    issued_at: datetime
    revoked_at: datetime | None = None
    revoke_reason: str | None = None
    verification_code: str


class ReadinessResponse(BaseSchema):
    """Whether the club can issue receipts at all, and what is missing.

    Asked before the form is shown rather than after it is submitted: telling
    somebody their tax number is missing once they have typed a donor's
    address is a poor way to run a settings check.
    """

    ready: bool
    missing: list[str]
    membership_fees_deductible: bool
