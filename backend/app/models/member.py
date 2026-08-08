import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, SoftDeleteMixin, TenantModel


class Member(TenantModel, AuditMixin, SoftDeleteMixin):
    """Club member record. Distinct from User (login account)."""

    __tablename__ = "members"
    __table_args__ = (
        # Delta sync pages with a keyset predicate on (updated_at, id);
        # tenant_id leads so each club scans its own contiguous range.
        # See alembic f2b9d84c1a07 and app/repositories/sync.py.
        Index("ix_members_sync", "tenant_id", "updated_at", "id"),
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
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)

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

    # When this member's device last collected a seed.
    #
    # Kept because it is the only way to find out whether the app's background
    # refresh actually reaches real phones. A seed goes stale on the calendar,
    # the refresh depends on Doze, standby buckets and each vendor's battery
    # manager, and none of that can be reasoned about from here — but a member
    # whose last fetch was a week ago will stand at the range with a code that
    # no longer verifies. Written on handout, read by nothing yet.
    last_seed_fetch_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class MemberFederationMembership(TenantModel, AuditMixin, SoftDeleteMixin):
    """A member's membership in an external federation (DSB, BDS, …).

    Its own table rather than columns on Member: a shooter is routinely in
    more than one federation, each with its own number and entry date, and
    federation reporting needs them as rows, not as a fixed pair of fields.
    """

    __tablename__ = "member_federation_memberships"
    __table_args__ = (
        # One row per federation and member — a second number in the same
        # federation is a data error, not a feature.
        UniqueConstraint("tenant_id", "member_id", "federation"),
        Index("ix_member_federation_memberships_member", "tenant_id", "member_id"),
    )

    member_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("members.id"), nullable=False, index=True
    )
    federation: Mapped[str] = mapped_column(String(100), nullable=False)
    federation_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    joined_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    left_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
