import uuid
from datetime import date

from pydantic import EmailStr, Field

from app.schemas.base import BaseSchema


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
