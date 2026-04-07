import uuid

from sqlalchemy import Boolean, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Discipline(Base, TimestampMixin):
    """A sport discipline definition. Global (not tenant-scoped) — shared
    across all tenants. Seeded with official DSB/BDS/ISSF disciplines.

    Tenants reference disciplines by ID when creating competitions/sessions.
    """

    __tablename__ = "disciplines"
    __table_args__ = (
        Index("ix_disciplines_federation", "federation"),
        Index("ix_disciplines_category", "category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # Unique machine-readable slug, e.g. "dsb-1.40-lg"
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Official name, e.g. "Luftgewehr"
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Short display name, e.g. "LG 10m"
    short_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Detailed description of rules, procedure, etc.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Sport federation: "DSB", "BDS", "ISSF", "WA" (World Archery), etc.
    federation: Mapped[str] = mapped_column(String(50), nullable=False)

    # Official discipline number within the federation, e.g. "1.40" (DSB SpO)
    federation_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Category: "Luftdruck", "Kleinkaliber", "Großkaliber", "Flinte", "Bogen", etc.
    category: Mapped[str] = mapped_column(String(100), nullable=False)

    # Distance, e.g. "10m", "25m", "50m", "100m"
    distance: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Caliber / weapon specification, e.g. "4.5mm", ".22 LR", "9mm"
    caliber: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Target type slug (references TargetType in the iOS app), e.g. "air_rifle_10m"
    target_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Scoring
    scoring_unit: Mapped[str] = mapped_column(String(50), nullable=False, default="Ringe")
    scoring_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="highest_wins")

    # Standard shot count per match/series (informational)
    shot_count: Mapped[int | None] = mapped_column(nullable=True)

    # Is this a standard/official discipline (vs user-created)?
    is_official: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Soft-hide deprecated disciplines
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
