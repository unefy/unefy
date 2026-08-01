from sqlalchemy import Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, SoftDeleteMixin, TenantModel


class MeasurementUnit(TenantModel, AuditMixin, SoftDeleteMixin):
    """A tenant-managed measurement unit for results, e.g. "Ringe", "Sekunden"."""

    __tablename__ = "measurement_units"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name"),
        Index("ix_measurement_units_tenant_active", "tenant_id", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ClubDiscipline(TenantModel, AuditMixin, SoftDeleteMixin):
    """A tenant-managed discipline, optionally imported from the global catalog."""

    __tablename__ = "club_disciplines"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name"),
        Index("ix_club_disciplines_tenant_active", "tenant_id", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Plain string on purpose — competitions/entries store unit names, not FKs
    default_unit: Mapped[str | None] = mapped_column(String(100), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
