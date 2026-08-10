import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantModel, TimestampMixin


class MembershipApplication(TenantModel, TimestampMixin):
    """Somebody asking to join, before anybody has decided.

    Deliberately not a `Member` with a pending status: admission is a decision
    the board takes, and a public form takes no decisions. Until it is accepted
    this row is an *applicant's* data — different purpose, different retention,
    and it must never appear in a member list, a due, or a §14 evaluation.

    No `AuditMixin`: nobody in the club created this row, an outsider did.
    Who decided, and when, is recorded in its own fields below.
    """

    __tablename__ = "membership_applications"
    __table_args__ = (
        Index("ix_applications_tenant_status", "tenant_id", "status"),
        # A decided application names who decided it; a pending one cannot.
        CheckConstraint(
            "(status = 'pending' AND decided_at IS NULL)"
            " OR (status IN ('accepted', 'rejected') AND decided_at IS NOT NULL)",
            name="ck_applications_decision_shape",
        ),
        # Acceptance is what creates the member, so exactly the accepted ones
        # carry the link. A rejected application must not point at anybody.
        CheckConstraint(
            "(status = 'accepted') = (member_id IS NOT NULL)",
            name="ck_applications_member_shape",
        ),
    )

    #: "pending" | "accepted" | "rejected".
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    # --- What the applicant told us. Mirrors the member fields it becomes. ---

    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(50), nullable=True)
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)

    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    #: What they wrote in the free field — why they want to join, questions.
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- What they asked for. Both optional: a club may offer neither. ---

    fee_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fee_types.id", ondelete="SET NULL"), nullable=True
    )
    division_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("divisions.id", ondelete="SET NULL"), nullable=True
    )

    # --- The direct debit mandate, if they granted one on the way in. ---

    iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    bic: Mapped[str | None] = mapped_column(String(11), nullable=True)
    account_holder: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: When they ticked the mandate box. The reference is assigned on
    #: acceptance — before that there is no membership to reference.
    sepa_mandate_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- Consent, recorded where it was given. ---

    #: Confirming the privacy notice is a precondition, not a consent: without
    #: it the form does not submit, so this is never false on a stored row.
    privacy_accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    #: Genuine consents — freely given, refusable, revocable later.
    consent_photos: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_newsletter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_directory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- The decision. ---

    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    #: Why it was rejected, for the club's own record. Never sent anywhere.
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: The member this became. Set only on acceptance.
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
