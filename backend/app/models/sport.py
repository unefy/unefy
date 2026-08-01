import uuid

from sqlalchemy import ARRAY, Boolean, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Sport(Base, TimestampMixin):
    """A sport offered on the platform. Global, maintained by platform admins.

    Deliberately a table rather than a code constant: adding a sport is data
    entry, not a release. The one exception is `modules`, which points at code
    and is validated against `app.core.modules.AVAILABLE_MODULES` on write.
    """

    __tablename__ = "sports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # Stable machine-readable key, e.g. "shooting". Referenced by config and
    # seeds, so it is immutable once rows point at it.
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Lucide icon name rendered by the web app, e.g. "Target".
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Sport modules this sport activates. Validated against the code registry.
    modules: Mapped[list[str]] = mapped_column(ARRAY(String(50)), nullable=False, default=list)


class CatalogUnit(Base, TimestampMixin):
    """A measurement unit offered as a default for a given sport.

    Copied into a club's own `measurement_units` at onboarding — clubs edit
    their copy, never this catalog.
    """

    __tablename__ = "catalog_units"
    __table_args__ = (Index("ix_catalog_units_sport_active", "sport_id", "is_active"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sport_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sports.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
