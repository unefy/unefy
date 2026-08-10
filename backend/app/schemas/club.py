import uuid
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import EmailStr, Field, field_validator

from app.schemas.base import BaseSchema


def _validate_timezone(value: str | None) -> str | None:
    """Accept only zones the runtime actually knows.

    A typo here would silently shift every attendance date by a day, so it is
    rejected at the edge rather than discovered months later in a proof.
    """
    if value is None:
        return None
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown time zone: {value}") from exc
    return value


class ClubResponse(BaseSchema):
    id: uuid.UUID
    name: str = Field(min_length=2, max_length=255)
    short_name: str | None = Field(default=None, max_length=50)
    slug: str

    # Contact
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    website: str | None = Field(default=None, max_length=500)

    # Address
    street: str | None = Field(default=None, max_length=255)
    zip_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=255)
    state: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=100)

    # Club details
    description: str | None = Field(default=None, max_length=5000)
    logo_url: str | None = Field(default=None, max_length=1024)
    founded_at: date | None = None
    registration_number: str | None = Field(default=None, max_length=100)
    registration_court: str | None = Field(default=None, max_length=255)
    tax_number: str | None = Field(default=None, max_length=100)
    tax_office: str | None = Field(default=None, max_length=255)
    is_nonprofit: bool = False
    nonprofit_since: date | None = None

    # SEPA creditor data
    sepa_creditor_id: str | None = Field(default=None, max_length=35)
    iban: str | None = Field(default=None, max_length=34)
    bic: str | None = Field(default=None, max_length=11)

    # Member numbers
    member_number_format: str = "{NUM:3}"
    member_number_next: int = 1

    # Member statuses
    member_statuses: str | None = None  # JSON string

    # IANA name, e.g. "Europe/Berlin". The club's calendar day.
    timezone: str = "Europe/Berlin"

    # Whether the club is organised in divisions (Sparten). Gates every
    # division picker in the UI.
    has_divisions: bool = False

    # Whether the public join form is open. Off until somebody turns it on:
    # it is the only way an unauthenticated stranger writes to the club.
    applications_enabled: bool = False


class ClubUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    short_name: str | None = Field(default=None, max_length=50)

    # Contact
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    website: str | None = Field(default=None, max_length=500)

    # Address
    street: str | None = Field(default=None, max_length=255)
    zip_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=255)
    state: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=100)

    # Club details
    description: str | None = Field(default=None, max_length=5000)
    logo_url: str | None = Field(default=None, max_length=1024)
    founded_at: date | None = None
    registration_number: str | None = Field(default=None, max_length=100)
    registration_court: str | None = Field(default=None, max_length=255)
    tax_number: str | None = Field(default=None, max_length=100)
    tax_office: str | None = Field(default=None, max_length=255)
    is_nonprofit: bool | None = None
    nonprofit_since: date | None = None

    # SEPA creditor data
    sepa_creditor_id: str | None = Field(default=None, max_length=35)
    iban: str | None = Field(default=None, max_length=34)
    bic: str | None = Field(default=None, max_length=11)

    # Member numbers
    member_number_format: str | None = Field(default=None, max_length=100)
    member_number_next: int | None = Field(default=None, ge=1)

    # Member statuses
    member_statuses: str | None = None  # JSON string

    # IANA name, e.g. "Europe/Berlin".
    timezone: str | None = Field(default=None, max_length=64)

    # Opening or closing the public join form.
    applications_enabled: bool | None = None

    _check_timezone = field_validator("timezone")(_validate_timezone)


class DivisionCreate(BaseSchema):
    """A new division (Sparte).

    `sport_id` is what makes a division more than a label — the §14 evaluation
    excludes evenings held by a division whose sport does not carry the
    shooting module.
    """

    name: str = Field(min_length=1, max_length=255)
    sport_id: uuid.UUID | None = None


class DivisionUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sport_id: uuid.UUID | None = None


class ClubSportsUpdate(BaseSchema):
    """The club's sports, replaced as a set."""

    sport_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    primary_sport_id: uuid.UUID | None = None
