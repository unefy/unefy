import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TargetType(Base, TimestampMixin):
    """Ring geometry of one shooting target. Global catalog, not tenant-scoped.

    The single source of truth for scoring. Both the backend scoring service and
    the Android engine work from these numbers, so a wrong value here is a wrong
    result everywhere — see `app.core.target_type_seeds` for the sources each row
    is taken from.

    `slug` is what `disciplines.target_type` already points at, e.g.
    "air_rifle_10m".
    """

    __tablename__ = "target_types"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    #: Outer diameter of each ring in mm, exactly 10 entries.
    #: Index 0 = ring 10 (innermost), index 9 = ring 1 (the whole scoring area).
    ring_diameters_mm: Mapped[list[float]] = mapped_column(JSONB, nullable=False)

    #: Inner ten / Mouche, used for tiebreaks. On the air rifle target this
    #: equals ring 10 itself.
    inner_ten_diameter_mm: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)

    #: Diameter of the black aiming mark (Spiegel) in mm.
    #:
    #: Stored as a length rather than "black from ring N": on the ISSF 50 m rifle
    #: target the black is 112.4 mm, which falls between ring 4 (106.4) and ring 3
    #: (122.4) and cannot be expressed as a ring number. It is also the scale
    #: anchor for photo recognition — the ellipse fitted to the black mark is what
    #: converts pixels to millimetres — so it has to be the exact physical value.
    black_diameter_mm: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)

    #: Bullet/pellet diameter in mm. Scoring is by the edge of the hole, so this
    #: enlarges every shot's scoring radius by half its value.
    caliber_diameter_mm: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    caliber_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    distance_m: Mapped[int] = mapped_column(nullable=False)

    #: Where the numbers come from, e.g. "ISSF Rifle Rules 6.3.4".
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
