"""The club's incoming invoices — a register, not bookkeeping."""

import math
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.file_types import HEAD_BYTES
from app.core.storage import CHUNK_SIZE, Storage, get_storage
from app.database import get_db_session
from app.dependencies import AuthContext, require_role
from app.models.incoming_invoice import IncomingInvoice
from app.schemas.incoming_invoice import (
    IncomingInvoiceResponse,
    IncomingInvoiceSummary,
    IncomingInvoiceUpdate,
    MarkPaidRequest,
)
from app.services.incoming_invoice import IncomingFile, IncomingInvoiceService

router = APIRouter()

#: Only what a browser can display without being able to run anything. XML is
#: deliberately absent: it may carry a stylesheet that renders it as HTML, and
#: from this origin that would be a script with the reader's session. It is
#: downloaded, like every other attachment.
_INLINE_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}


def _service(auth: AuthContext, session: AsyncSession, storage: Storage) -> IncomingInvoiceService:
    return IncomingInvoiceService(session, auth, storage)


def _payload(invoice: IncomingInvoice) -> dict[str, Any]:
    """Only the fields the response declares.

    Reading every column instead — the obvious first version — reaches
    `updated_at`, which SQLAlchemy marks for re-fetching after an UPDATE
    because the column has an `onupdate`. That first read then issues a query
    from the response serialiser, outside the async context that could run it,
    and every second write to the same row failed with `MissingGreenlet`.
    Pydantic touches only what it was asked for, and none of it is deferred.
    """
    return IncomingInvoiceResponse.model_validate(invoice).model_dump(mode="json")


@router.get("")
async def list_invoices(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100),
    year: int | None = Query(default=None, ge=2000, le=2100),
    status: str | None = Query(default=None, pattern="^(open|paid|cancelled)$"),
) -> dict[str, Any]:
    invoices, total = await _service(auth, session, storage).list_invoices(
        year=year, status=status, offset=(page - 1) * per_page, limit=per_page
    )
    return {
        "data": [_payload(invoice) for invoice in invoices],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total else 0,
        },
    }


@router.get("/summary")
async def invoice_summary(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
    year: int | None = Query(default=None, ge=2000, le=2100),
) -> dict[str, Any]:
    """Declared before `/{invoice_id}`, which would swallow "summary"."""
    summary = await _service(auth, session, storage).summary(year=year)
    return {"data": IncomingInvoiceSummary.model_validate(summary).model_dump(mode="json")}


@router.post("", status_code=201)
async def upload_invoice(
    file: Annotated[UploadFile, File()],
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Take the file in, and read it if it can be read.

    No fields in the request. A structured e-invoice fills them itself, and
    for a scan they are typed afterwards on the record — asking for them up
    front would mean standing at the form with the invoice in hand before the
    document is anywhere safe.
    """
    invoice = await _service(auth, session, storage).upload(
        await _incoming(file), settings=settings
    )
    return {"data": _payload(invoice)}


@router.get("/{invoice_id}")
async def get_invoice(
    invoice_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> dict[str, Any]:
    invoice = await _service(auth, session, storage).get(invoice_id)
    return {"data": _payload(invoice)}


@router.patch("/{invoice_id}")
async def update_invoice(
    invoice_id: uuid.UUID,
    data: IncomingInvoiceUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> dict[str, Any]:
    invoice = await _service(auth, session, storage).update(invoice_id, data)
    return {"data": _payload(invoice)}


@router.post("/{invoice_id}/pay")
async def mark_invoice_paid(
    invoice_id: uuid.UUID,
    data: MarkPaidRequest,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> dict[str, Any]:
    """Its own route rather than a status in the PATCH body.

    Paying is an event with a date, and the two fields that record it only
    ever move together — a status set through the general update would let
    them drift apart.
    """
    invoice = await _service(auth, session, storage).mark_paid(invoice_id, data.paid_on)
    return {"data": _payload(invoice)}


@router.post("/{invoice_id}/reopen")
async def reopen_invoice(
    invoice_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> dict[str, Any]:
    invoice = await _service(auth, session, storage).reopen(invoice_id)
    return {"data": _payload(invoice)}


@router.post("/{invoice_id}/cancel")
async def cancel_invoice(
    invoice_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> dict[str, Any]:
    """Withdrawn or replaced by the supplier. Stays in the register, outside
    the totals — a charge that vanished would leave a gap nobody can explain."""
    invoice = await _service(auth, session, storage).cancel(invoice_id)
    return {"data": _payload(invoice)}


@router.delete("/{invoice_id}", status_code=204)
async def delete_invoice(
    invoice_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> Response:
    """Admin and above, unlike the rest of the register.

    Cancelling is what a board member does to an invoice that turned out
    wrong; deleting removes the document itself, and that is a different act.
    """
    await _service(auth, session, storage).delete(invoice_id)
    return Response(status_code=204)


@router.get("/{invoice_id}/file")
async def download_invoice_file(
    invoice_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> StreamingResponse:
    """The invoice as it arrived. Every download passes through here — there
    are no public buckets and no guessable URLs."""
    service = _service(auth, session, storage)
    invoice = await service.get(invoice_id)

    disposition = "inline" if invoice.content_type in _INLINE_TYPES else "attachment"
    return StreamingResponse(
        service.open_file(invoice),
        media_type=invoice.content_type,
        headers={
            "Content-Disposition": (
                f'{disposition}; filename="{_ascii_filename(invoice.original_filename)}"; '
                f"filename*=UTF-8''{quote(invoice.original_filename)}"
            ),
            "Content-Length": str(invoice.byte_size),
            # The detected type, and no sniffing for a better idea in the
            # bytes: together they keep an uploaded file from being run as
            # something else.
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


async def _incoming(file: UploadFile) -> IncomingFile:
    """Turn an upload into something the service can read twice over.

    The head first, so the type is decided before anything is stored, then the
    file rewound and handed over whole. Starlette has already spooled it to a
    temporary file, which is why reading it twice is cheap.
    """
    head = await file.read(HEAD_BYTES)
    await file.seek(0)
    return IncomingFile(
        filename=file.filename or "rechnung",
        head=head,
        stream=_chunks(file),
        declared_size=file.size,
    )


async def _chunks(file: UploadFile) -> AsyncIterator[bytes]:
    while chunk := await file.read(CHUNK_SIZE):
        yield chunk


def _ascii_filename(value: str) -> str:
    """The fallback name, for clients that ignore RFC 5987."""
    safe = "".join(c if c.isascii() and (c.isalnum() or c in "-_.") else "-" for c in value)
    return safe.strip("-") or "rechnung"
