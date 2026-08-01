import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, SoftDeleteMixin, TenantModel


class FeeType(TenantModel, AuditMixin, SoftDeleteMixin):
    """A fee schedule entry (Beitragssatz), e.g. "Erwachsene", "Jugend"."""

    __tablename__ = "fee_types"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name"),
        Index("ix_fee_types_tenant_active", "tenant_id", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Amount per interval in the club currency (EUR)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # yearly | half_yearly | quarterly | monthly | one_time
    interval: Mapped[str] = mapped_column(String(20), nullable=False, default="yearly")

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MemberFee(TenantModel, AuditMixin, SoftDeleteMixin):
    """Assignment of a fee type to a member, with validity range."""

    __tablename__ = "member_fees"
    __table_args__ = (
        Index("ix_member_fees_tenant_member", "tenant_id", "member_id"),
        Index("ix_member_fees_tenant_fee_type", "tenant_id", "fee_type_id"),
    )

    member_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("members.id"), nullable=False)
    fee_type_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("fee_types.id"), nullable=False)

    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Due(TenantModel, AuditMixin, SoftDeleteMixin):
    """An assessed open item (Sollstellung) for a member and billing period."""

    __tablename__ = "dues"
    __table_args__ = (
        # Idempotency of assessment runs: one due per member/fee type/period
        UniqueConstraint("tenant_id", "member_id", "fee_type_id", "period_start"),
        Index("ix_dues_tenant_status", "tenant_id", "status"),
        Index("ix_dues_tenant_member", "tenant_id", "member_id"),
        Index("ix_dues_tenant_period", "tenant_id", "period_start"),
    )

    member_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("members.id"), nullable=False)
    fee_type_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("fee_types.id"), nullable=False)

    # Snapshot of the fee at assessment time (fee types may change later)
    fee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    # open | paid | cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")

    paid_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)
