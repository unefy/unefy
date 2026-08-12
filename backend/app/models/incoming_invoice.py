import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, SoftDeleteMixin, TenantModel

#: Where the figures came from. Not decoration: a number read out of a
#: structured e-invoice is the supplier's own statement, and a number somebody
#: typed off a scan is a reading of it. The list shows which is which, because
#: only one of them is worth trusting without a second look.
INVOICE_SOURCES = ("manual", "zugferd", "xrechnung")

#: `open` and `paid` mirror the vocabulary the dues side already uses, so a
#: treasurer meets one set of words across the whole product. `cancelled` is
#: for an invoice that was withdrawn or replaced by the supplier.
INVOICE_STATUSES = ("open", "paid", "cancelled")


class IncomingInvoice(TenantModel, AuditMixin, SoftDeleteMixin):
    """One invoice the club received, and the file it arrived as.

    A register — a Rechnungseingangsbuch — not bookkeeping. It answers what
    came in, from whom, for how much, and whether it has been paid; it holds no
    accounts and produces no journal entries.

    **The file is stored first and the figures may follow.** A scan carries no
    machine-readable data, so `gross_amount` and the rest are nullable and the
    record is simply incomplete until somebody fills them in. Refusing the
    upload until the form validates would be the wrong trade: the invoice
    exists either way, and the one outcome to avoid is losing the document
    because a field was missing.

    Never a second copy of the file. `storage_key` points into the same store
    the library writes to, and the club's quota counts both — see
    `services/storage_usage.py`.
    """

    __tablename__ = "incoming_invoices"
    __table_args__ = (
        # The check a register exists for: the same invoice, entered twice,
        # paid twice. Partial, so it only bites once both parts are known —
        # a scan waiting to be typed up has neither.
        Index(
            "uq_incoming_invoices_supplier_number",
            "tenant_id",
            "supplier_name",
            "invoice_number",
            unique=True,
            postgresql_where="deleted_at IS NULL "
            "AND supplier_name IS NOT NULL AND invoice_number IS NOT NULL",
        ),
        Index("ix_incoming_invoices_tenant_date", "tenant_id", "invoice_date"),
        Index("ix_incoming_invoices_tenant_status", "tenant_id", "status"),
        UniqueConstraint("tenant_id", "storage_key"),
        CheckConstraint(
            "status IN ('open', 'paid', 'cancelled')",
            name="ck_incoming_invoices_status",
        ),
        CheckConstraint(
            "source IN ('manual', 'zugferd', 'xrechnung')",
            name="ck_incoming_invoices_source",
        ),
        CheckConstraint(
            "gross_amount IS NULL OR gross_amount >= 0",
            name="ck_incoming_invoices_gross_not_negative",
        ),
    )

    # --- Who sent it ---

    #: Free text rather than a supplier table. A register records what the
    #: paper says; a creditor with an identity of its own belongs to the
    #: bookkeeping this deliberately is not.
    supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    #: The VAT identification number, when the e-invoice carries one. Kept
    #: because it is the only part of a supplier that is actually an identifier.
    supplier_vat_id: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # --- What it says ---

    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    #: Gross is the one that matters and the one a club always has; net and tax
    #: are filled from an e-invoice and stay empty for a scan nobody split up.
    gross_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    #: ISO 4217. Almost always EUR, and stored anyway: an invoice in CHF that
    #: silently reads as euros is a wrong number in the annual figures.
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Where it stands ---

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    paid_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    #: `manual` until a parser says otherwise. Set per record rather than
    #: derived at read time, because the file can be re-read later with a
    #: better parser and the field then states what was actually used.
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")

    # --- The file it arrived as ---

    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)

    #: The same file uploaded twice is the same bytes. Not unique on its own —
    #: a club may legitimately receive an identical monthly invoice — but it is
    #: what a duplicate warning can point at.
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @property
    def is_complete(self) -> bool:
        """Whether the register can count this row.

        Supplier, number, date and gross — the four a treasurer needs to say
        the invoice was received and what it was for. Anything short of that is
        a filed document waiting to be typed up, and the list says so.
        """
        return all(
            (
                self.supplier_name,
                self.invoice_number,
                self.invoice_date,
                self.gross_amount is not None,
            )
        )
