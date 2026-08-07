import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, TenantModel, TimestampMixin

# Function levels. A `club` function is held once per club, a `division`
# function once per division (Sparte) — the assignment then carries the
# division it applies to.
FUNCTION_LEVELS = ("club", "division")


class CatalogFunction(Base, TimestampMixin):
    """A club office (Amt) offered as a default, e.g. "Kassier".

    Global, maintained by platform admins. Copied by value into a club's own
    `functions` list at onboarding — clubs edit their copy, never this catalog.
    Same mechanic as `CatalogUnit` → `measurement_units`.
    """

    __tablename__ = "catalog_functions"
    __table_args__ = (Index("ix_catalog_functions_sport_active", "sport_id", "is_active"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # NULL = a general office every club has (Vorsitz, Kassier, …); set = an
    # office specific to one sport (Schützenmeister).
    sport_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sports.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Stable machine-readable key for seeds and onboarding payloads.
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="club")

    # A recommendation only — the UI suggests it when assigning the function,
    # auth roles are never coupled automatically.
    suggested_role: Mapped[str | None] = mapped_column(String(20), nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Function(TenantModel, AuditMixin):
    """A club-owned office (Amt), e.g. "1. Vorsitzende:r" or a custom one.

    The club's list is fully its own: seeded from the catalog at onboarding,
    then renamed, extended or deactivated freely — no FK back to the catalog.
    """

    __tablename__ = "functions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name"),
        Index("ix_functions_tenant_active", "tenant_id", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="club")
    suggested_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Deactivate instead of delete once assignments (also historic) exist.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MemberFunction(TenantModel, AuditMixin):
    """One term of office (Amtszeit) of a member in a function.

    A member can hold the same function repeatedly — each term is its own row.
    `valid_to = NULL` means currently in office. History is never deleted,
    only ended; hard deletes exist solely for correcting typos.
    """

    __tablename__ = "member_functions"
    __table_args__ = (
        Index("ix_member_functions_tenant_member", "tenant_id", "member_id"),
        Index(
            "ix_member_functions_tenant_function_division",
            "tenant_id",
            "function_id",
            "division_id",
        ),
    )

    member_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )

    # RESTRICT: a function with terms (even historic ones) must be deactivated,
    # not deleted — the service turns the violation into a 409.
    function_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("functions.id", ondelete="RESTRICT"), nullable=False
    )

    # Required when the function has level `division`; enforced in the service
    # because the DB cannot see the function's level from here.
    division_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("divisions.id", ondelete="SET NULL"), nullable=True, index=True
    )

    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    # e.g. "kommissarisch"
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
