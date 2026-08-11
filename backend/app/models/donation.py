import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, TenantModel

#: What was given. A membership fee is only ever certifiable when the club's
#: recognised purposes allow it — see `Tenant.membership_fees_deductible`.
DONATION_KINDS = ("geldzuwendung", "mitgliedsbeitrag")

#: Which notice recognises the club.
EXEMPTION_KINDS = ("freistellungsbescheid", "feststellung_60a")


class DonationReceipt(TenantModel, AuditMixin):
    """A donation receipt, frozen as it was issued.

    A prescribed form, not a letter the club composes: its content follows the
    official template of the tax administration, and every field on it is
    there because the template puts it there. That is exactly why it lives in
    code rather than in `DocumentTemplate` — a free-text version of this would
    be an invitation to produce a receipt the donor cannot use.

    Everything the receipt asserts is copied in at issuing time, including the
    club's own tax data. The Freistellungsbescheid changes, the recognised
    purposes change, the club's address changes — and a receipt from 2024 has
    to keep saying what was true in 2024.

    Never edited. A mistake is revoked and re-issued, because the donor still
    holds the paper and the tax office may already have seen it.
    """

    __tablename__ = "donation_receipts"
    __table_args__ = (
        Index("ix_donation_receipts_tenant_received", "tenant_id", "received_on"),
        Index("ix_donation_receipts_tenant_member", "tenant_id", "member_id"),
        CheckConstraint("amount > 0", name="ck_donation_receipts_amount_positive"),
        CheckConstraint(
            "kind IN ('geldzuwendung', 'mitgliedsbeitrag')",
            name="ck_donation_receipts_kind",
        ),
    )

    # --- The donor ---
    #
    # A donor need not be a member, so the name and address are stored rather
    # than referenced. When they are a member, the link is kept as well — the
    # club wants the receipts on the member's page — but the printed name
    # stays what it was on the day.

    member_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    donor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    donor_address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- What was given ---

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    received_on: Mapped[date] = mapped_column(Date, nullable=False)
    #: One of `DONATION_KINDS`.
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    #: Whether this is a waiver of reimbursement of expenses. The template asks
    #: for it explicitly and the answer belongs on the paper either way — a
    #: blank box would be an unanswered question, not a "no".
    is_expense_waiver: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- The club, as it was on the day ---

    club_name: Mapped[str] = mapped_column(String(255), nullable=False)
    club_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: One of `EXEMPTION_KINDS`.
    exemption_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    exemption_date: Mapped[date] = mapped_column(Date, nullable=False)
    #: Only set for a Freistellungsbescheid; a §60a determination covers no
    #: assessment period.
    exemption_period: Mapped[int | None] = mapped_column(nullable=True)
    tax_office: Mapped[str] = mapped_column(String(255), nullable=False)
    tax_number: Mapped[str] = mapped_column(String(100), nullable=False)
    purposes: Mapped[str] = mapped_column(String(500), nullable=False)

    # --- Issuing ---

    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    issued_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)

    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Short and unguessable, never the UUID — the QR carries it and the public
    #: check page accepts it. Globally unique, because that page has no tenant
    #: to scope by.
    verification_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    #: SHA-256 over everything the receipt asserts.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
