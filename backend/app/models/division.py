import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, TenantModel


class Division(TenantModel, AuditMixin):
    """A club division (Sparte) and the sport it practises.

    Every club has at least one, even single-sport clubs: they get a single
    primary division named after the club, and `tenants.has_divisions = False`
    hides the concept in the UI. One code path instead of two, and a club can
    switch on divisions later without a data migration.
    """

    __tablename__ = "divisions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name"),
        Index("ix_divisions_tenant_primary", "tenant_id", "is_primary"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # The sport is the reason divisions exist; without it a division is just a
    # label. Nullable only so a deleted sport does not cascade away club data.
    sport_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sports.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Exactly one per tenant. Drives defaults where a single division must be
    # assumed (e.g. a club that has not switched divisions on).
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
