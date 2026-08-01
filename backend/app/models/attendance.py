import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    AuditMixin,
    SoftDeleteMixin,
    TenantModel,
    TimestampMixin,
)

# Every check-in proves two things: *who* was there and *where/when*. The
# methods differ only in which of the two is technically secured rather than
# asserted by a human.
ATTENDANCE_METHODS = ("manual", "staff_scan", "venue_scan", "self", "nfc_tap")

# What the API actually accepts today. The remaining methods exist in the model
# so that `assurance` can be reasoned about as one scale, but they are rejected
# by validation until they are built.
IMPLEMENTED_METHODS = ("manual",)

ASSURANCE_LEVELS = ("low", "medium", "high")

# Derived server-side, never accepted from a client: the level of proof is a
# property of the procedure, not a claim the caller gets to make.
ASSURANCE_BY_METHOD = {
    "manual": "low",
    "staff_scan": "high",
}


class AttendanceSession(TenantModel, AuditMixin, SoftDeleteMixin):
    """A window of time during which members can check in at one place.

    Deliberately not hung off `Event`: shooting practice happens every Tuesday
    without anyone maintaining calendar entries for it, and `Event` has no
    concept of recurrence. The link stays optional.
    """

    __tablename__ = "attendance_sessions"
    __table_args__ = (
        Index("ix_attendance_sessions_tenant_opens", "tenant_id", "opens_at"),
        Index("ix_attendance_sessions_tenant_status", "tenant_id", "status"),
        Index("ix_attendance_sessions_tenant_division", "tenant_id", "division_id"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)

    division_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("divisions.id", ondelete="SET NULL"), nullable=True
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("events.id", ondelete="SET NULL"), nullable=True
    )

    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # "open" | "closed"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")

    # The supervising member (Standaufsicht). A member, not a user: the person
    # on duty need not have a login.
    supervisor_member_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("members.id"), nullable=True
    )

    # Closing freezes the session: no further check-ins, no corrections. This
    # is the "Einfrieren" half of assurance level 0 — a late entry has to be
    # recognisable as a late entry.
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    # Assurance level 1. Written when the hash chain is built; unused for now,
    # the column exists so adding the chain needs no migration.
    close_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AttendanceRecord(TenantModel, AuditMixin, SoftDeleteMixin):
    """One member's attendance at one session — the evidence layer.

    Retained for years (`tenants.attendance_retention_years`). Never hard-deleted
    outside the retention job: corrections soft-delete and leave an audit entry
    with a reason.
    """

    __tablename__ = "attendance_records"
    __table_args__ = (
        # Partial rather than a plain unique constraint: a soft-deleted record
        # is history, and a member wrongly removed must be able to check in
        # again without resurrecting the corrected row.
        Index(
            "uq_attendance_records_tenant_session_member",
            "tenant_id",
            "session_id",
            "member_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        # Carries the 12-month evaluation for the §14 proof.
        Index("ix_attendance_tenant_member_date", "tenant_id", "member_id", "occurred_on"),
        Index("ix_attendance_records_tenant_session", "tenant_id", "session_id"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("members.id"), nullable=False)

    # Denormalised calendar day, taken from the session's opening date. All
    # records of one session share it, which is exactly what "18 appointments
    # in 12 months" counts.
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)

    checked_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Device time vs. server time, kept apart so an offline-buffered scan stays
    # honest about when it actually happened. Unused until the scanner exists.
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    method: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    assurance: Mapped[str] = mapped_column(String(10), nullable=False, default="low")

    # Who vouched for this check-in. Mandatory for `manual` and `staff_scan`.
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Outlives the context row (see retention). Once the technical context has
    # expired, what remains provable is: "a technical context with this
    # fingerprint existed for this check-in, it was checked, it was unremarkable."
    context_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # "ok" | "suspicious" | "unchecked"
    context_verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)


class AttendanceCheckinContext(TenantModel, TimestampMixin):
    """Technical context of a check-in — the short-lived layer.

    Separate table because it lives on a different clock: weeks, not years, and
    it is hard-deleted by its own job over `expires_at`. Written only by the
    scanning paths; a manual check-in by the supervisor has no device context
    to record.
    """

    __tablename__ = "attendance_checkin_contexts"
    __table_args__ = (Index("ix_attendance_contexts_expires", "expires_at"),)

    attendance_record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("attendance_records.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # An install id rather than a device fingerprint: the phone model is close
    # to worthless as a fraud signal, while "one installation checked in twelve
    # different members tonight" is the pattern that matters — and it is less
    # personally identifying.
    install_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    staff_device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    code_counter: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
