import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, SoftDeleteMixin, TenantModel


class Member(TenantModel, AuditMixin, SoftDeleteMixin):
    """Club member record. Distinct from User (login account)."""

    __tablename__ = "members"
    __table_args__ = (
        UniqueConstraint("tenant_id", "member_number"),
        Index("ix_members_tenant_status", "tenant_id", "status"),
        Index("ix_members_tenant_name", "tenant_id", "last_name", "first_name"),
        # Unique and indexed: every scan resolves a ref to a member through it,
        # and two members sharing one would check the wrong person in.
        Index(
            "uq_members_tenant_attendance_ref",
            "tenant_id",
            "attendance_ref",
            unique=True,
            postgresql_where=text("attendance_ref IS NOT NULL"),
        ),
    )

    # Member number (auto-generated from tenant format)
    member_number: Mapped[str] = mapped_column(String(50), nullable=False)

    # Personal
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(50), nullable=True)
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Address
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True, default="Deutschland")

    # Membership
    joined_at: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    left_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Banking / SEPA direct debit
    iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    bic: Mapped[str | None] = mapped_column(String(11), nullable=True)
    account_holder: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sepa_mandate_reference: Mapped[str | None] = mapped_column(String(35), nullable=True)
    sepa_mandate_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Optional link to User (for self-service portal)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)

    # Tenant-wide pseudonym, used by the rotating attendance code. Kept off the
    # primary key on purpose: the code is displayed as a QR that anyone in the
    # room can photograph, and a photograph must not hand out a member id.
    # Null until the member first asks for a seed — there is no reason to mint
    # one for a club that never turns scanning on.
    attendance_ref: Mapped[str | None] = mapped_column(String(16), nullable=True)
