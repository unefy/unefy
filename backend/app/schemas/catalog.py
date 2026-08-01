import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema

# --- MeasurementUnit ---


class MeasurementUnitCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=100)
    symbol: str | None = Field(default=None, max_length=20)
    is_active: bool = True


class MeasurementUnitUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    symbol: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None


class MeasurementUnitResponse(BaseSchema):
    id: uuid.UUID
    name: str
    symbol: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --- ClubDiscipline ---


class ClubDisciplineCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=255)
    short_name: str | None = Field(default=None, max_length=100)
    default_unit: str | None = Field(default=None, max_length=100)
    is_active: bool = True


class ClubDisciplineUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    short_name: str | None = Field(default=None, max_length=100)
    default_unit: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class ClubDisciplineResponse(BaseSchema):
    id: uuid.UUID
    name: str
    short_name: str | None = None
    default_unit: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DisciplineImportRequest(BaseSchema):
    discipline_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
