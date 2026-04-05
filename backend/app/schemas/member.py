import uuid
from datetime import date, datetime

from pydantic import EmailStr, Field

from app.schemas.base import BaseSchema, PaginationMeta


class MemberBulkDelete(BaseSchema):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class MemberCreate(BaseSchema):
    first_name: str = Field(min_length=1, max_length=255)
    last_name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    mobile: str | None = Field(default=None, max_length=50)
    birthday: date | None = None
    street: str | None = Field(default=None, max_length=255)
    zip_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=255)
    state: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=100)
    joined_at: date | None = None  # defaults to today in service
    status: str = Field(default="active", max_length=50)
    category: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=5000)


class MemberUpdate(BaseSchema):
    first_name: str | None = Field(default=None, min_length=1, max_length=255)
    last_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    mobile: str | None = Field(default=None, max_length=50)
    birthday: date | None = None
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


class MemberResponse(BaseSchema):
    id: uuid.UUID
    member_number: str
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None
    birthday: date | None = None
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
    user_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class MemberListResponse(BaseSchema):
    data: list[MemberResponse]
    meta: PaginationMeta
