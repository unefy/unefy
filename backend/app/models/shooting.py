"""The shooting-sport module — §14 WaffG proof on top of core attendance.

Everything here lives behind `require_module("shooting")`: attendance is core,
but what makes it a *Schießnachweis* — per-record shooting details, the
evaluation rules, the issued certificate — is module territory. A table-tennis
club never sees these tables.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, TenantModel

# Typed column rather than JSONB (unlike `competitions.sport_data`): the §14
# evaluation filters by weapon category, and that filter must be indexable.
WEAPON_CATEGORIES = ("kurzwaffe", "langwaffe", "luftdruck")

CERTIFICATE_RESULTS = ("passed", "failed")


class ShootingRecordDetail(TenantModel, AuditMixin):
    """1:1 extension of an AttendanceRecord with what was shot.

    A separate table instead of columns on the record: the record is core and
    serves every club, the detail only exists where the shooting module is
    active. Deleted with its record (CASCADE) — a detail without attendance
    is a claim about nothing.
    """

    __tablename__ = "shooting_record_details"
    __table_args__ = (
        CheckConstraint(
            "weapon_category IN ('kurzwaffe', 'langwaffe', 'luftdruck')",
            name="ck_shooting_details_weapon_category",
        ),
        CheckConstraint("rounds_fired >= 0", name="ck_shooting_details_rounds_nonnegative"),
    )

    attendance_record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("attendance_records.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    club_discipline_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("club_disciplines.id", ondelete="SET NULL"), nullable=True
    )

    weapon_category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rounds_fired: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ShootingProofRule(TenantModel, AuditMixin):
    """One evaluation threshold — configuration, never code.

    The familiar rule ("18 times in 12 months, or at least once a month")
    varies by state and authority, and §14 WaffG has been amended repeatedly.
    So the numbers live in rows a club maintains, keyed by `rule_key`, and no
    migration ever ships a threshold (see the plan's "Offene Punkte").

    The two criteria are alternatives: the proof passes when *either* is met,
    matching the usual "X appointments or one per month" phrasing. A rule that
    wants only one criterion leaves the other empty; at least one must be set.
    """

    __tablename__ = "shooting_proof_rules"
    __table_args__ = (
        Index("uq_shooting_rules_tenant_key", "tenant_id", "rule_key", unique=True),
        CheckConstraint(
            "min_total_days IS NOT NULL OR min_distinct_months IS NOT NULL",
            name="ck_shooting_rules_has_criterion",
        ),
        CheckConstraint("window_months > 0", name="ck_shooting_rules_window_positive"),
    )

    rule_key: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)

    # The rolling evaluation window, counted back from the reference day.
    window_months: Mapped[int] = mapped_column(Integer, nullable=False, default=12)

    # Criterion A: at least this many distinct shooting days in the window.
    min_total_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Criterion B: at least this many distinct calendar months with a shooting
    # day in the window.
    min_distinct_months: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ShootingProofCertificate(TenantModel, AuditMixin):
    """The issued proof, frozen at the moment of issuing.

    Issued by a human, never automatically (Art. 22 DSGVO and plain club
    hygiene — the evaluation proposes, a board member signs). `record_ids` and
    `content_hash` pin the document to exactly the records that were counted:
    even after one of them is corrected — or removed by the retention job —
    it stays provable what this certificate was based on.
    """

    __tablename__ = "shooting_proof_certificates"
    __table_args__ = (
        Index("ix_shooting_certificates_tenant_member", "tenant_id", "member_id"),
        CheckConstraint("result IN ('passed', 'failed')", name="ck_shooting_certificates_result"),
    )

    member_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("members.id"), nullable=False)

    rule_key: Mapped[str] = mapped_column(String(50), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    session_count: Mapped[int] = mapped_column(Integer, nullable=False)
    months_covered: Mapped[int] = mapped_column(Integer, nullable=False)

    result: Mapped[str] = mapped_column(String(10), nullable=False)

    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    issued_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)

    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Which records were evaluated, as plain UUIDs — deliberately not foreign
    # keys, so the retention job can remove the records years later without
    # tearing the certificate's anchor out.
    record_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    # SHA-256 over the canonical JSON of what was certified.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Short and unguessable, never the UUID: this is what the QR carries and
    # what the public verify page accepts. Globally unique because that page
    # is unauthenticated and has no tenant context to scope by.
    verification_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)

    # PDF in storage, once rendering exists.
    document_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Assurance level 2 (qualified electronic seal, eIDAS Art. 35) — deferred,
    # the column exists so it can be added without a migration.
    seal: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
