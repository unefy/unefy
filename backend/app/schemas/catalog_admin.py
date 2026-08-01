import uuid

from pydantic import Field, field_validator

from app.core.modules import unknown_modules
from app.schemas.base import BaseSchema

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
SCORING_MODES = ("highest_wins", "lowest_wins", "fastest_time")


def _validate_modules(value: list[str]) -> list[str]:
    """Reject module names with no implementation behind them.

    `sports.modules` is the one field where admin-editable data points at code.
    An unvalidated value would silently do nothing, which is worse than a
    rejected write.
    """
    unknown = unknown_modules(value)
    if unknown:
        raise ValueError(f"Unknown modules: {', '.join(sorted(unknown))}")
    return value


# --- Sports ---


class SportCreate(BaseSchema):
    key: str = Field(min_length=2, max_length=50, pattern=SLUG_PATTERN)
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    icon: str | None = Field(default=None, max_length=50)
    sort_order: int = 0
    is_active: bool = True
    modules: list[str] = Field(default_factory=list)

    _check_modules = field_validator("modules")(_validate_modules)


class SportUpdate(BaseSchema):
    # `key` is intentionally absent: other rows and config reference it, so it
    # is immutable once created.
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    icon: str | None = Field(default=None, max_length=50)
    sort_order: int | None = None
    is_active: bool | None = None
    modules: list[str] | None = None

    @field_validator("modules")
    @classmethod
    def check_modules(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _validate_modules(value)


class SportResponse(BaseSchema):
    id: uuid.UUID
    key: str
    name: str
    description: str | None
    icon: str | None
    sort_order: int
    is_active: bool
    modules: list[str]
    unit_count: int = 0
    discipline_count: int = 0


# --- Catalog units ---


class CatalogUnitCreate(BaseSchema):
    sport_id: uuid.UUID
    name: str = Field(min_length=1, max_length=100)
    symbol: str | None = Field(default=None, max_length=20)
    sort_order: int = 0
    is_active: bool = True


class CatalogUnitUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    symbol: str | None = Field(default=None, max_length=20)
    sort_order: int | None = None
    is_active: bool | None = None


class CatalogUnitResponse(BaseSchema):
    id: uuid.UUID
    sport_id: uuid.UUID
    name: str
    symbol: str | None
    sort_order: int
    is_active: bool


# --- Catalog disciplines ---


class CatalogDisciplineCreate(BaseSchema):
    sport_id: uuid.UUID
    slug: str = Field(min_length=2, max_length=100, pattern=SLUG_PATTERN)
    name: str = Field(min_length=2, max_length=255)
    short_name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    federation: str = Field(min_length=1, max_length=50)
    federation_id: str | None = Field(default=None, max_length=50)
    category: str = Field(min_length=1, max_length=100)
    distance: str | None = Field(default=None, max_length=50)
    caliber: str | None = Field(default=None, max_length=100)
    target_type: str | None = Field(default=None, max_length=100)
    scoring_unit: str = Field(default="Ringe", min_length=1, max_length=50)
    scoring_mode: str = Field(default="highest_wins")
    shot_count: int | None = Field(default=None, ge=1, le=1000)
    is_official: bool = True
    is_active: bool = True

    @field_validator("scoring_mode")
    @classmethod
    def check_scoring_mode(cls, value: str) -> str:
        # Each mode needs a ranking implementation, so this stays a closed set
        # in code rather than free text.
        if value not in SCORING_MODES:
            raise ValueError(f"scoring_mode must be one of: {', '.join(SCORING_MODES)}")
        return value


class CatalogDisciplineUpdate(BaseSchema):
    sport_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=255)
    short_name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    federation: str | None = Field(default=None, min_length=1, max_length=50)
    federation_id: str | None = Field(default=None, max_length=50)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    distance: str | None = Field(default=None, max_length=50)
    caliber: str | None = Field(default=None, max_length=100)
    target_type: str | None = Field(default=None, max_length=100)
    scoring_unit: str | None = Field(default=None, min_length=1, max_length=50)
    scoring_mode: str | None = None
    shot_count: int | None = Field(default=None, ge=1, le=1000)
    is_official: bool | None = None
    is_active: bool | None = None

    @field_validator("scoring_mode")
    @classmethod
    def check_scoring_mode(cls, value: str | None) -> str | None:
        if value is not None and value not in SCORING_MODES:
            raise ValueError(f"scoring_mode must be one of: {', '.join(SCORING_MODES)}")
        return value


class CatalogDisciplineResponse(BaseSchema):
    id: uuid.UUID
    sport_id: uuid.UUID | None
    slug: str
    name: str
    short_name: str | None
    description: str | None
    federation: str
    federation_id: str | None
    category: str
    distance: str | None
    caliber: str | None
    target_type: str | None
    scoring_unit: str
    scoring_mode: str
    shot_count: int | None
    is_official: bool
    is_active: bool
