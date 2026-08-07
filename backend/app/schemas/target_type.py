import uuid

from pydantic import Field

from app.schemas.base import BaseSchema


class TargetTypeResponse(BaseSchema):
    """Ring geometry of one target, as the clients mirror it.

    `ring_diameters_mm` holds exactly 10 outer diameters in millimetres,
    index 0 = ring 10 (innermost), index 9 = ring 1.
    """

    id: uuid.UUID
    slug: str
    name: str
    ring_diameters_mm: list[float]
    inner_ten_diameter_mm: float
    black_diameter_mm: float
    #: Default caliber. Overridable per series and per shot — the same sheet is
    #: shot with .22 and 9 mm, sometimes both at once.
    caliber_diameter_mm: float
    caliber_name: str | None
    distance_m: int
    source: str | None
    is_active: bool


class CaliberResponse(BaseSchema):
    """One entry of the caliber picker."""

    key: str
    name: str
    diameter_mm: float = Field(gt=0, le=30)
