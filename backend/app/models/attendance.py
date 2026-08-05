import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
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
# asserted by a human — except `self`, where the two collapse: the person
# asserting and the person asserted about are the same, so nothing is secured.
ATTENDANCE_METHODS = ("manual", "staff_scan", "venue_scan", "self", "nfc_tap")

# What a check-in can actually be recorded as today. `venue_scan` and `nfc_tap`
# exist in the taxonomy above so `assurance` can be reasoned about as one scale,
# and are rejected until they are built.
#
# `self` is never *accepted* — a client cannot claim it any more than it can claim
# an assurance level. It is derived: see `AttendanceService._method_for`.
IMPLEMENTED_METHODS = ("manual", "staff_scan", "self")

ASSURANCE_LEVELS = ("low", "medium", "high")

# Where a record comes from. `club` is the default and the strong case: the
# session, its supervisor and the close chain stand behind it. `external` is a
# member's own entry about a visit to some other range — no session, no
# witness, and the honest levels to go with that: method `self`, assurance
# `low`. The §14 evaluation counts both and says which is which.
RECORD_ORIGINS = ("club", "external")

# Derived server-side, never accepted from a client: the level of proof is a
# property of the procedure, not a claim the caller gets to make.
ASSURANCE_BY_METHOD = {
    "manual": "low",
    "staff_scan": "high",
    # The record whose subject is also its author. Weakest of the built methods,
    # and the honest level for it: nobody but the person themselves says they
    # were there. It exists because the supervisor's own attendance has no other
    # route — a QR needs two devices and they are holding the reader.
    "self": "low",
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
        #
        # Guests are unconstrained by it, because Postgres treats NULLs as
        # distinct. That is the behaviour wanted here: two guests may well share
        # a name, and nothing about a guest identifies them well enough to
        # refuse the second one.
        Index(
            "uq_attendance_records_tenant_session_member",
            "tenant_id",
            "session_id",
            "member_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        # Exactly one of the two, enforced by the database rather than by
        # whichever service happens to write the row. A record that is neither
        # is not attendance, and one that is both is a contradiction about who
        # was there.
        CheckConstraint(
            "(member_id IS NOT NULL) <> (guest_name IS NOT NULL)",
            name="ck_attendance_records_member_xor_guest",
        ),
        # A club record hangs off a session; an external one names the range
        # instead and always belongs to a member — a guest has no proof to
        # keep, and nobody keeps one for them. Enforced by the database, so no
        # write path can produce a record that is neither.
        CheckConstraint(
            "(origin = 'club' AND session_id IS NOT NULL AND external_location IS NULL)"
            " OR (origin = 'external' AND session_id IS NULL"
            " AND member_id IS NOT NULL AND external_location IS NOT NULL)",
            name="ck_attendance_records_origin_shape",
        ),
        # One external entry per member and day. Two ranges on one day are
        # still one §14 day, and a second row would only pad the list.
        Index(
            "uq_attendance_records_external_member_day",
            "tenant_id",
            "member_id",
            "occurred_on",
            unique=True,
            postgresql_where=text("origin = 'external' AND deleted_at IS NULL"),
        ),
        # Carries the 12-month evaluation for the §14 proof.
        Index("ix_attendance_tenant_member_date", "tenant_id", "member_id", "occurred_on"),
        Index("ix_attendance_records_tenant_session", "tenant_id", "session_id"),
    )

    # Null only for an external self-entry — see the origin CHECK above.
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=True
    )

    # "club" | "external" — where this record's credibility comes from.
    origin: Mapped[str] = mapped_column(String(20), nullable=False, default="club")

    # The foreign range's name, as the member gave it. Only for `external`.
    external_location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Null for a guest. The club still has to know who was on the range —
    # supervision duty and insurance do not care about membership — but a guest
    # has no member record and must never count towards anyone's §14 proof.
    # The proof query joins members, so guests fall out of it by construction.
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("members.id"), nullable=True
    )

    # Set instead of `member_id`, never alongside it — see the CHECK below.
    guest_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

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
