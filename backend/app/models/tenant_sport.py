import uuid

from sqlalchemy import Boolean, ForeignKey, Index, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantModel, TimestampMixin


class TenantSport(TenantModel, TimestampMixin):
    """The sports a club actually runs.

    Many-to-many on purpose: a Turnverein with a shooting section is a real
    club, not an edge case, and the single-sport shortcut would have to be
    migrated away the first time one signs up.

    This is the edge that makes sport modules resolvable. `sports.modules` maps
    a sport to the code modules it activates; without a tenant-to-sport link
    there was no way to ask which modules a given club has. A club's active
    modules are the union over its sports.
    """

    __tablename__ = "tenant_sports"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sport_id", name="uq_tenant_sports_tenant_sport"),
        Index("ix_tenant_sports_tenant_primary", "tenant_id", "is_primary"),
    )

    sport_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("sports.id"),
        nullable=False,
        index=True,
    )

    # Which sport represents the club when one has to be picked — a default
    # discipline, an icon, a report heading. Not enforced as unique: a club with
    # no primary is valid, and two is a display detail, not a data corruption.
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
