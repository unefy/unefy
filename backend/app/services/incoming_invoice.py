"""The register: a file arrives, its figures follow, and it gets paid."""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
    ValidationError,
)
from app.core.file_types import UnsupportedFileTypeError, detect_content_type
from app.core.storage import ObjectTooLargeError, Storage, StoredObject, build_key
from app.dependencies import AuthContext
from app.models.incoming_invoice import IncomingInvoice
from app.schemas.incoming_invoice import IncomingInvoiceUpdate
from app.services import einvoice
from app.services.storage_usage import stored_bytes


@dataclass(frozen=True)
class IncomingFile:
    """An upload, reduced to what the service needs.

    `head` is the first few kilobytes, already read, so the type can be decided
    before a byte is stored. `stream` yields the whole file including that head.
    Same shape as the library's — deliberately, because it is the same job.
    """

    filename: str
    head: bytes
    stream: AsyncIterator[bytes]
    declared_size: int | None = None


class IncomingInvoiceService:
    def __init__(self, session: AsyncSession, auth: AuthContext, storage: Storage) -> None:
        self.session = session
        self.auth = auth
        self.tenant_id = auth.tenant
        self.storage = storage

    # --- Reading ---

    def _scope(self) -> Any:
        return and_(
            IncomingInvoice.tenant_id == self.tenant_id,
            IncomingInvoice.deleted_at.is_(None),
        )

    async def list_invoices(
        self,
        *,
        year: int | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[IncomingInvoice], int]:
        query = select(IncomingInvoice).where(self._scope())
        query = self._filtered(query, year=year, status=status)

        total = await self.session.execute(
            self._filtered(
                select(func.count()).select_from(IncomingInvoice).where(self._scope()),
                year=year,
                status=status,
            )
        )
        # Newest first, and a row with no date yet at the very top: it is the
        # one still waiting for somebody, and burying it under a year of filed
        # invoices is how it stays unfinished.
        rows = await self.session.execute(
            query.order_by(
                IncomingInvoice.invoice_date.is_(None).desc(),
                IncomingInvoice.invoice_date.desc(),
                IncomingInvoice.uploaded_at.desc(),
            )
            .offset(offset)
            .limit(limit)
            .execution_options(populate_existing=True)
        )
        return list(rows.scalars().all()), int(total.scalar_one())

    def _filtered(self, query: Select[Any], *, year: int | None, status: str | None) -> Select[Any]:
        if year is not None:
            # An invoice with no date yet belongs to no year, so it drops out
            # of a filtered view rather than landing in an arbitrary one.
            query = query.where(
                and_(
                    IncomingInvoice.invoice_date >= date(year, 1, 1),
                    IncomingInvoice.invoice_date <= date(year, 12, 31),
                )
            )
        if status is not None:
            query = query.where(IncomingInvoice.status == status)
        return query

    async def get(self, invoice_id: uuid.UUID) -> IncomingInvoice:
        """One invoice, with its attributes actually loaded.

        `populate_existing` because a session that has seen this row before
        hands back the instance it already holds, expired attributes and all —
        and the first read of one then issues a query from wherever the caller
        happens to be, which for a response serialiser is outside the async
        context that could run it.
        """
        result = await self.session.execute(
            select(IncomingInvoice)
            .where(self._scope())
            .where(IncomingInvoice.id == invoice_id)
            .execution_options(populate_existing=True)
        )
        invoice = result.scalar_one_or_none()
        if invoice is None:
            raise NotFoundError("Invoice not found")
        return invoice

    async def summary(self, year: int | None = None) -> dict[str, Any]:
        """What the year cost, and what of it is still owed.

        Cancelled invoices are left out of both totals — the club decided it
        does not owe them — and counted separately so the decision stays
        visible. Incomplete rows have no amount to add and are counted so the
        total can be read as "of what has been entered".
        """
        query = (
            select(
                IncomingInvoice.status,
                func.count(),
                func.coalesce(func.sum(IncomingInvoice.gross_amount), 0),
            )
            .where(self._scope())
            .group_by(IncomingInvoice.status)
        )
        if year is not None:
            query = query.where(
                and_(
                    IncomingInvoice.invoice_date >= date(year, 1, 1),
                    IncomingInvoice.invoice_date <= date(year, 12, 31),
                )
            )
        result = await self.session.execute(query)
        rows = {status: (int(count), Decimal(total)) for status, count, total in result.all()}

        open_count, open_total = rows.get("open", (0, Decimal("0")))
        paid_count, paid_total = rows.get("paid", (0, Decimal("0")))
        cancelled_count, cancelled_total = rows.get("cancelled", (0, Decimal("0")))

        incomplete = await self.session.execute(
            self._filtered(
                select(func.count()).select_from(IncomingInvoice).where(self._scope()),
                year=year,
                status=None,
            ).where(
                or_(
                    IncomingInvoice.gross_amount.is_(None),
                    IncomingInvoice.supplier_name.is_(None),
                    IncomingInvoice.invoice_number.is_(None),
                    IncomingInvoice.invoice_date.is_(None),
                )
            )
        )

        return {
            "year": year,
            "open_count": open_count,
            "open_amount": open_total,
            "paid_count": paid_count,
            "paid_amount": paid_total,
            "cancelled_count": cancelled_count,
            "cancelled_amount": cancelled_total,
            "total_amount": open_total + paid_total,
            "incomplete_count": int(incomplete.scalar_one()),
        }

    def open_file(self, invoice: IncomingInvoice) -> AsyncIterator[bytes]:
        return self.storage.open(invoice.storage_key)

    # --- Writing ---

    async def upload(self, file: IncomingFile, *, settings: Settings) -> IncomingInvoice:
        """Store the file, read what it says about itself, keep the row.

        In that order and without a validation gate. The invoice exists the
        moment it arrives; refusing it because no amount could be determined
        would lose the document over a field a person can type in a minute.
        """
        content_type = self._detect(file)
        stored = await self._store(file, settings=settings)

        parsed = None
        if _may_carry_data(content_type):
            # The whole file, read back from the store rather than buffered in
            # the request: an e-invoice's XML can sit anywhere in a PDF, and
            # the parser needs it complete.
            content = await self._read_back(stored.key)
            parsed = einvoice.parse(content, content_type)

        invoice = IncomingInvoice(
            tenant_id=self.tenant_id,
            storage_key=stored.key,
            original_filename=file.filename[:255],
            content_type=content_type,
            byte_size=stored.byte_size,
            checksum_sha256=stored.checksum_sha256,
            uploaded_by_user_id=self.auth.user_id,
            uploaded_at=datetime.now(UTC),
            created_by=self.auth.user_id,
            updated_by=self.auth.user_id,
            source=parsed.source if parsed else "manual",
            currency=(parsed.currency if parsed and parsed.currency else "EUR"),
        )
        if parsed:
            invoice.invoice_number = parsed.invoice_number
            invoice.invoice_date = parsed.invoice_date
            invoice.due_date = parsed.due_date
            invoice.supplier_name = parsed.supplier_name
            invoice.supplier_vat_id = parsed.supplier_vat_id
            invoice.net_amount = parsed.net_amount
            invoice.tax_amount = parsed.tax_amount
            invoice.gross_amount = parsed.gross_amount

        await self._refuse_duplicate(invoice.supplier_name, invoice.invoice_number)

        self.session.add(invoice)
        await self.session.flush()
        return invoice

    async def update(self, invoice_id: uuid.UUID, data: IncomingInvoiceUpdate) -> IncomingInvoice:
        """Complete or correct a record. The file is never touched.

        A wrong figure is corrected in place rather than revoked and re-entered
        the way a document is: nobody outside the club has ever seen this row,
        and the paper it was typed from has not changed.
        """
        invoice = await self.get(invoice_id)
        changes = data.model_dump(exclude_unset=True)

        supplier = changes.get("supplier_name", invoice.supplier_name)
        number = changes.get("invoice_number", invoice.invoice_number)
        if (supplier, number) != (invoice.supplier_name, invoice.invoice_number):
            await self._refuse_duplicate(supplier, number, excluding=invoice.id)

        for field, value in changes.items():
            setattr(invoice, field, value)

        # Typing the figures by hand makes them a person's reading of the
        # document, whatever the file once said about itself.
        if changes and invoice.source != "manual" and _touches_figures(changes):
            invoice.source = "manual"

        invoice.updated_by = self.auth.user_id
        await self.session.flush()
        return invoice

    async def mark_paid(self, invoice_id: uuid.UUID, paid_on: date | None) -> IncomingInvoice:
        invoice = await self.get(invoice_id)
        if invoice.status == "cancelled":
            raise ConflictError("A cancelled invoice cannot be paid")
        if invoice.gross_amount is None:
            # Without an amount "paid" says nothing anybody can check, and the
            # register's whole job is to be checkable.
            raise ValidationError("The invoice has no amount yet")

        invoice.status = "paid"
        invoice.paid_on = paid_on or datetime.now(UTC).date()
        invoice.updated_by = self.auth.user_id
        await self.session.flush()
        return invoice

    async def reopen(self, invoice_id: uuid.UUID) -> IncomingInvoice:
        """For the payment that was recorded against the wrong invoice."""
        invoice = await self.get(invoice_id)
        invoice.status = "open"
        invoice.paid_on = None
        invoice.updated_by = self.auth.user_id
        await self.session.flush()
        return invoice

    async def cancel(self, invoice_id: uuid.UUID) -> IncomingInvoice:
        invoice = await self.get(invoice_id)
        invoice.status = "cancelled"
        invoice.paid_on = None
        invoice.updated_by = self.auth.user_id
        await self.session.flush()
        return invoice

    async def delete(self, invoice_id: uuid.UUID) -> None:
        """Soft-delete the row and remove the file.

        The bytes go because the club is charged for them and because an
        invoice nobody can reach is not a document the club keeps; the row
        stays so a deletion is visible to whoever looks for the gap in the
        numbers.
        """
        invoice = await self.get(invoice_id)
        invoice.deleted_at = datetime.now(UTC)
        invoice.updated_by = self.auth.user_id
        await self.session.flush()
        await self.storage.delete(invoice.storage_key)

    # --- Helpers ---

    def _detect(self, file: IncomingFile) -> str:
        try:
            return detect_content_type(file.head, file.filename)
        except UnsupportedFileTypeError as exc:
            raise UnsupportedMediaTypeError(str(exc)) from exc

    async def _store(self, file: IncomingFile, *, settings: Settings) -> StoredObject:
        """Size and quota, then the bytes. Every check before the write is a
        refusal that costs nothing.

        Size and checksum come back from the writer rather than being counted
        here: they are what actually went to disk, and a `Content-Length` is a
        claim the row has no business recording.
        """
        max_upload = settings.MAX_UPLOAD_BYTES
        used = await stored_bytes(self.session, self.tenant_id)
        remaining = max(settings.TENANT_STORAGE_QUOTA_BYTES - used, 0)

        if file.declared_size is not None and file.declared_size > max_upload:
            raise PayloadTooLargeError(
                f"The file is larger than the limit of {max_upload} bytes",
                code="UPLOAD_TOO_LARGE",
            )
        if file.declared_size is not None and file.declared_size > remaining:
            raise PayloadTooLargeError(
                "The club's storage quota is exhausted", code="STORAGE_QUOTA_EXCEEDED"
            )

        key = build_key(self.tenant_id)
        try:
            stored = await self.storage.put(key, file.stream, max_bytes=min(max_upload, remaining))
        except ObjectTooLargeError as exc:
            if remaining <= max_upload:
                raise PayloadTooLargeError(
                    "The club's storage quota is exhausted", code="STORAGE_QUOTA_EXCEEDED"
                ) from exc
            raise PayloadTooLargeError(
                f"The file is larger than the limit of {max_upload} bytes",
                code="UPLOAD_TOO_LARGE",
            ) from exc
        return stored

    async def _read_back(self, key: str) -> bytes:
        """The stored file, in memory, for the parser.

        Bounded by the upload limit that already applied, so this cannot be
        made to allocate more than a club is allowed to send in one request.
        """
        chunks = [chunk async for chunk in self.storage.open(key)]
        return b"".join(chunks)

    async def _refuse_duplicate(
        self,
        supplier_name: str | None,
        invoice_number: str | None,
        *,
        excluding: uuid.UUID | None = None,
    ) -> None:
        """The check the register exists for.

        Only when both parts are known: a scan waiting to be typed up has
        neither, and refusing those would refuse every scan after the first.
        """
        if not supplier_name or not invoice_number:
            return

        query = (
            select(IncomingInvoice.id)
            .where(self._scope())
            .where(IncomingInvoice.supplier_name == supplier_name)
            .where(IncomingInvoice.invoice_number == invoice_number)
        )
        if excluding is not None:
            query = query.where(IncomingInvoice.id != excluding)

        existing = (await self.session.execute(query)).scalars().first()
        if existing is not None:
            raise ConflictError(
                f"{supplier_name} has already sent invoice {invoice_number}",
                code="INVOICE_ALREADY_RECORDED",
            )


#: Only these can carry structured data. A JPEG of a paper invoice cannot, and
#: handing it to the parser would be work with a known answer.
def _may_carry_data(content_type: str) -> bool:
    return content_type in {"application/pdf", "application/xml", "text/xml", "text/plain"}


def _touches_figures(changes: dict[str, Any]) -> bool:
    return bool(
        changes.keys()
        & {
            "invoice_number",
            "invoice_date",
            "due_date",
            "supplier_name",
            "supplier_vat_id",
            "net_amount",
            "tax_amount",
            "gross_amount",
            "currency",
        }
    )
