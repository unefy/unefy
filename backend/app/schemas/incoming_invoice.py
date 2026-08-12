"""I/O for the incoming-invoice register."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import BaseSchema


class IncomingInvoiceUpdate(BaseSchema):
    """Completing or correcting a record. Every field optional.

    The file is not among them: an invoice is the document that arrived, and
    replacing it under an existing row would leave the figures asserting
    something the file no longer says. A wrong file is deleted and uploaded
    again.
    """

    supplier_name: str | None = Field(default=None, max_length=255)
    supplier_vat_id: str | None = Field(default=None, max_length=30)
    invoice_number: str | None = Field(default=None, max_length=100)
    invoice_date: date | None = None
    due_date: date | None = None
    gross_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    net_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    tax_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    note: str | None = Field(default=None, max_length=2000)


class MarkPaidRequest(BaseSchema):
    #: Defaults to today in the club's zone when the caller does not say.
    paid_on: date | None = None


class IncomingInvoiceResponse(BaseSchema):
    id: uuid.UUID

    supplier_name: str | None = None
    supplier_vat_id: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None

    gross_amount: Decimal | None = None
    net_amount: Decimal | None = None
    tax_amount: Decimal | None = None
    currency: str

    status: str
    paid_on: date | None = None
    note: str | None = None

    #: `manual`, `zugferd` or `xrechnung` — where these figures came from. A
    #: number the supplier stated in machine-readable form and a number
    #: somebody read off a scan are not worth the same, and the list says which.
    source: str

    #: Whether the register can count this row: supplier, number, date, amount.
    is_complete: bool

    original_filename: str
    content_type: str
    byte_size: int
    uploaded_at: datetime


class IncomingInvoiceSummary(BaseSchema):
    """Totals for a year. Cancelled is outside both, and stated separately."""

    year: int | None = None
    open_count: int
    open_amount: Decimal
    paid_count: int
    paid_amount: Decimal
    cancelled_count: int
    cancelled_amount: Decimal
    #: Open plus paid. What the club was invoiced, minus what it cancelled.
    total_amount: Decimal
    #: Rows still missing one of the four. The totals cannot see them.
    incomplete_count: int
