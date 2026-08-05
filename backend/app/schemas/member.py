import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import EmailStr, Field

from app.schemas.base import BaseSchema, PaginationMeta

Gender = Literal["male", "female", "diverse"]


class MemberBulkDelete(BaseSchema):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class MemberCreate(BaseSchema):
    first_name: str = Field(min_length=1, max_length=255)
    last_name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    mobile: str | None = Field(default=None, max_length=50)
    birthday: date | None = None
    gender: Gender | None = None
    street: str | None = Field(default=None, max_length=255)
    zip_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=255)
    state: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=100)
    joined_at: date | None = None  # defaults to today in service
    status: str = Field(default="active", max_length=50)
    category: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=5000)
    iban: str | None = Field(default=None, max_length=34)
    bic: str | None = Field(default=None, max_length=11)
    account_holder: str | None = Field(default=None, max_length=255)
    sepa_mandate_reference: str | None = Field(default=None, max_length=35)
    sepa_mandate_date: date | None = None


class MemberUpdate(BaseSchema):
    first_name: str | None = Field(default=None, min_length=1, max_length=255)
    last_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    mobile: str | None = Field(default=None, max_length=50)
    birthday: date | None = None
    gender: Gender | None = None
    street: str | None = Field(default=None, max_length=255)
    zip_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=255)
    state: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=100)
    joined_at: date | None = None
    left_at: date | None = None
    status: str | None = Field(default=None, max_length=50)
    category: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=5000)
    iban: str | None = Field(default=None, max_length=34)
    bic: str | None = Field(default=None, max_length=11)
    account_holder: str | None = Field(default=None, max_length=255)
    sepa_mandate_reference: str | None = Field(default=None, max_length=35)
    sepa_mandate_date: date | None = None


class MemberResponse(BaseSchema):
    id: uuid.UUID
    member_number: str
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
    state: str | None = None
    country: str | None = None
    joined_at: date
    left_at: date | None = None
    status: str
    category: str | None = None
    notes: str | None = None
    iban: str | None = None
    bic: str | None = None
    account_holder: str | None = None
    sepa_mandate_reference: str | None = None
    sepa_mandate_date: date | None = None
    user_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class MemberListResponse(BaseSchema):
    data: list[MemberResponse]
    meta: PaginationMeta


class FederationMembershipResponse(BaseSchema):
    id: uuid.UUID
    member_id: uuid.UUID
    federation: str
    federation_number: str | None = None
    joined_at: date | None = None
    left_at: date | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class MemberDirectoryEntry(BaseSchema):
    """What one member may see about another.

    A separate schema rather than a subset of `MemberResponse`, because the
    guard has to be structural: adding a field to the admin response must not
    silently widen what the directory exposes. Contact details, address,
    birthday and banking are absent by design — sharing those between members
    needs a legal basis and a club-level setting, not a default.
    """

    id: uuid.UUID
    first_name: str
    last_name: str
    category: str | None = None
