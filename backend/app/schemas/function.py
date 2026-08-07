import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.base import BaseSchema

FunctionLevel = Literal["club", "division"]
SuggestedRole = Literal["owner", "admin", "board", "member"]

# --- Function (the club's own list of offices) ---


class FunctionCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=255)
    level: FunctionLevel = "club"
    suggested_role: SuggestedRole | None = None
    sort_order: int = 0
    is_active: bool = True


class FunctionUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    level: FunctionLevel | None = None
    suggested_role: SuggestedRole | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class FunctionResponse(BaseSchema):
    id: uuid.UUID
    name: str
    level: FunctionLevel
    suggested_role: SuggestedRole | None = None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --- MemberFunction (one term of office) ---


class MemberFunctionCreate(BaseSchema):
    function_id: uuid.UUID
    division_id: uuid.UUID | None = None
    valid_from: date
    valid_to: date | None = None
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def check_range(self) -> "MemberFunctionCreate":
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to must not be before valid_from")
        return self


class MemberFunctionUpdate(BaseSchema):
    division_id: uuid.UUID | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    note: str | None = Field(default=None, max_length=500)


class MemberFunctionResponse(BaseSchema):
    id: uuid.UUID
    member_id: uuid.UUID
    function_id: uuid.UUID
    function_name: str
    level: FunctionLevel
    division_id: uuid.UUID | None = None
    division_name: str | None = None
    valid_from: date
    valid_to: date | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Holders (Vorstandsliste / Besetzung zum Stichtag) ---


class FunctionHolderResponse(BaseSchema):
    assignment_id: uuid.UUID
    function_id: uuid.UUID
    function_name: str
    level: FunctionLevel
    sort_order: int
    division_id: uuid.UUID | None = None
    division_name: str | None = None
    member_id: uuid.UUID
    member_first_name: str
    member_last_name: str
    valid_from: date
    valid_to: date | None = None
    note: str | None = None
