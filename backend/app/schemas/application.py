import uuid
from datetime import date, datetime

from pydantic import EmailStr, Field, model_validator

from app.schemas.base import BaseSchema

GENDER_PATTERN = "^(male|female|diverse)$"


class ApplicationSubmit(BaseSchema):
    """The public join form.

    Only what an applicant can truthfully say about themselves. Status,
    decision and member number are not in here and never will be — the form
    asks to join, it does not admit anybody.
    """

    first_name: str = Field(min_length=1, max_length=255)
    last_name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    mobile: str | None = Field(default=None, max_length=50)
    birthday: date | None = None
    gender: str | None = Field(default=None, pattern=GENDER_PATTERN)

    street: str | None = Field(default=None, max_length=255)
    zip_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=100)

    message: str | None = Field(default=None, max_length=2000)

    fee_type_id: uuid.UUID | None = None
    division_id: uuid.UUID | None = None

    iban: str | None = Field(default=None, max_length=34)
    bic: str | None = Field(default=None, max_length=11)
    account_holder: str | None = Field(default=None, max_length=255)
    #: Ticking the mandate box. The reference is assigned on acceptance —
    #: before that there is no membership to reference.
    grant_sepa_mandate: bool = False

    #: The privacy notice must be confirmed for the form to submit. A
    #: precondition rather than a consent: without it there is no lawful basis
    #: to store the application at all.
    privacy_accepted: bool

    consent_photos: bool = False
    consent_newsletter: bool = False
    consent_directory: bool = False

    @model_validator(mode="after")
    def validate_shape(self) -> "ApplicationSubmit":
        if not self.privacy_accepted:
            raise ValueError("The privacy notice must be accepted")
        # A mandate without an account is a promise nobody can collect on.
        if self.grant_sepa_mandate and not self.iban:
            raise ValueError("A direct debit mandate needs an IBAN")
        return self


class ApplicationDecision(BaseSchema):
    """Why an application was rejected — the club's own record."""

    note: str | None = Field(default=None, max_length=2000)


class ApplicationResponse(BaseSchema):
    id: uuid.UUID
    status: str
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None
    birthday: date | None = None
    gender: str | None = None
    street: str | None = None
    zip_code: str | None = None
    city: str | None = None
    country: str | None = None
    message: str | None = None
    fee_type_id: uuid.UUID | None = None
    division_id: uuid.UUID | None = None
    #: Whether a mandate was granted. The IBAN itself is not in the list
    #: response — see `ApplicationDetailResponse`.
    has_sepa_mandate: bool = False
    privacy_accepted_at: datetime
    consent_photos: bool
    consent_newsletter: bool
    consent_directory: bool
    decided_at: datetime | None = None
    decision_note: str | None = None
    member_id: uuid.UUID | None = None
    created_at: datetime


class ApplicationDetailResponse(ApplicationResponse):
    """One application, with the bank details.

    Split from the list response for the same reason the member list splits
    them: a board member scanning twenty applications has no business being
    handed twenty IBANs.
    """

    iban: str | None = None
    bic: str | None = None
    account_holder: str | None = None


class PublicFeeType(BaseSchema):
    """A fee as the join form may show it — no internals, no activity flag."""

    id: uuid.UUID
    name: str
    amount: str
    interval: str


class PublicDivision(BaseSchema):
    id: uuid.UUID
    name: str


class JoinFormResponse(BaseSchema):
    """What the public form needs to render, and nothing more.

    Deliberately no member count, no contact person, no anything that would
    turn a join page into a reconnaissance tool.
    """

    club_name: str
    fee_types: list[PublicFeeType]
    divisions: list[PublicDivision]
    has_divisions: bool
