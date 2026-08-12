"""Reading a structured e-invoice — ZUGFeRD/Factur-X and XRechnung.

Two shapes arrive at a German club since e-invoicing became mandatory for
business senders in 2025:

- a **PDF/A-3 with the invoice XML attached** (ZUGFeRD, Factur-X). The PDF is
  what a person reads; the attachment is the same invoice as data.
- a **bare XML file** (XRechnung), in one of two syntaxes — UN/CEFACT CII or
  OASIS UBL. XRechnung is a profile, not a third syntax, so supporting both
  syntaxes covers it.

Only the handful of fields a register needs is read: number, dates, supplier,
totals, currency. Nothing here validates the invoice against a standard and
nothing computes — an amount is taken as the document states it, because the
supplier's own total is the one the club owes.

**Parsing never raises into the request.** A file that is not an e-invoice, or
is one and is malformed, yields `None`; the upload then keeps the file and
leaves the fields for a person. An import path that can fail the upload would
turn "this scan is unusual" into "your invoice was rejected".
"""

import io
import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from defusedxml.ElementTree import fromstring as safe_fromstring

if TYPE_CHECKING:  # Only ever a type here — pypdf itself is imported lazily.
    from collections.abc import Mapping

logger = logging.getLogger(__name__)

#: The attachment names the two standards use. Matched case-insensitively;
#: senders differ on capitalisation and have done since ZUGFeRD 1.0.
EINVOICE_ATTACHMENTS = (
    "factur-x.xml",
    "zugferd-invoice.xml",
    "xrechnung.xml",
    "order-x.xml",
)

CII_NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}

UBL_NS = {
    "inv": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}


@dataclass(frozen=True)
class ParsedInvoice:
    """What the document says about itself. Every field optional.

    A sender may leave out a due date or state only a gross total, and a
    parser that insisted would reject valid invoices. Missing means the
    document did not say so — never that it said zero.
    """

    source: str
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    supplier_name: str | None = None
    supplier_vat_id: str | None = None
    net_amount: Decimal | None = None
    tax_amount: Decimal | None = None
    gross_amount: Decimal | None = None
    currency: str | None = None


def parse(content: bytes, content_type: str) -> ParsedInvoice | None:
    """The one entry point: bytes in, fields or nothing out."""
    try:
        if content_type == "application/pdf":
            xml = _attachment_from_pdf(content)
            return _parse_xml(xml, source="zugferd") if xml else None
        if _looks_like_xml(content):
            return _parse_xml(content, source="xrechnung")
    except Exception:  # A malformed file is a normal event here, not a fault.
        logger.info("einvoice_parse_failed", exc_info=True)
    return None


def _looks_like_xml(content: bytes) -> bool:
    head = content[:512].lstrip()
    return head.startswith(b"<?xml") or head.startswith(b"<")


def _attachment_from_pdf(content: bytes) -> bytes | None:
    """The invoice XML out of a PDF/A-3.

    Imported inside the function on purpose: pypdf is only needed when a PDF
    actually turns up, and the import costs more than the check that decides
    whether it is needed.
    """
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    attachments: Mapping[str, list[bytes]] = reader.attachments
    for name, payloads in attachments.items():
        if name.lower() in EINVOICE_ATTACHMENTS and payloads:
            return payloads[0]
    # Some senders attach the XML under their own name. One attachment that
    # parses as an invoice is better than giving up on a filename.
    for payloads in attachments.values():
        if payloads and _looks_like_xml(payloads[0]):
            return payloads[0]
    return None


def _parse_xml(content: bytes, *, source: str) -> ParsedInvoice | None:
    root = safe_fromstring(content)
    tag = root.tag
    if "CrossIndustryInvoice" in tag:
        return _parse_cii(root, source=source)
    if tag.endswith("}Invoice") or tag == "Invoice":
        # A bare UBL file is an XRechnung; the same syntax inside a PDF is not.
        return _parse_ubl(root, source=source)
    return None


def _parse_cii(root: Any, *, source: str) -> ParsedInvoice:
    """UN/CEFACT Cross Industry Invoice — what ZUGFeRD and Factur-X carry."""
    settlement = "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement"
    totals = f"{settlement}/ram:SpecifiedTradeSettlementHeaderMonetarySummation"
    seller = (
        "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty"
    )

    return ParsedInvoice(
        source=source,
        invoice_number=_text(root, "rsm:ExchangedDocument/ram:ID", CII_NS),
        invoice_date=_cii_date(root, "rsm:ExchangedDocument/ram:IssueDateTime"),
        due_date=_cii_date(
            root, f"{settlement}/ram:SpecifiedTradePaymentTerms/ram:DueDateDateTime"
        ),
        supplier_name=_text(root, f"{seller}/ram:Name", CII_NS),
        supplier_vat_id=_seller_vat_cii(root, seller),
        net_amount=_decimal(root, f"{totals}/ram:TaxBasisTotalAmount", CII_NS),
        tax_amount=_decimal(root, f"{totals}/ram:TaxTotalAmount", CII_NS),
        # `GrandTotalAmount` is the invoice total; `DuePayableAmount` is what
        # remains after prepayments. The club owes the latter, so it wins when
        # both are there.
        gross_amount=(
            _decimal(root, f"{totals}/ram:DuePayableAmount", CII_NS)
            or _decimal(root, f"{totals}/ram:GrandTotalAmount", CII_NS)
        ),
        currency=_text(root, f"{settlement}/ram:InvoiceCurrencyCode", CII_NS),
    )


def _parse_ubl(root: Any, *, source: str) -> ParsedInvoice:
    """OASIS UBL — the other syntax an XRechnung may be written in."""
    totals = "cac:LegalMonetaryTotal"
    seller = "cac:AccountingSupplierParty/cac:Party"

    return ParsedInvoice(
        source=source,
        invoice_number=_text(root, "cbc:ID", UBL_NS),
        invoice_date=_date(_text(root, "cbc:IssueDate", UBL_NS)),
        due_date=_date(_text(root, "cbc:DueDate", UBL_NS))
        or _date(_text(root, "cac:PaymentMeans/cbc:PaymentDueDate", UBL_NS)),
        supplier_name=(
            _text(root, f"{seller}/cac:PartyLegalEntity/cbc:RegistrationName", UBL_NS)
            or _text(root, f"{seller}/cac:PartyName/cbc:Name", UBL_NS)
        ),
        supplier_vat_id=_text(root, f"{seller}/cac:PartyTaxScheme/cbc:CompanyID", UBL_NS),
        net_amount=_decimal(root, f"{totals}/cbc:TaxExclusiveAmount", UBL_NS),
        tax_amount=_decimal(root, "cac:TaxTotal/cbc:TaxAmount", UBL_NS),
        gross_amount=(
            _decimal(root, f"{totals}/cbc:PayableAmount", UBL_NS)
            or _decimal(root, f"{totals}/cbc:TaxInclusiveAmount", UBL_NS)
        ),
        currency=_text(root, "cbc:DocumentCurrencyCode", UBL_NS),
    )


def _seller_vat_cii(root: Any, seller: str) -> str | None:
    """The seller's VAT number, which CII files under a scheme code.

    A seller carries several registrations — `VA` is the VAT identification
    number, `FC` the tax number the tax office issued. Only the first is an
    identifier anywhere but at that one office, so only it is kept. Senders
    are inconsistent about the attribute, so a single unlabelled registration
    is taken at face value.
    """
    registrations = root.findall(f"{seller}/ram:SpecifiedTaxRegistration/ram:ID", CII_NS)
    for registration in registrations:
        if (registration.get("schemeID") or "").upper() == "VA":
            return (registration.text or "").strip() or None
    if len(registrations) == 1 and registrations[0].get("schemeID") is None:
        return (registrations[0].text or "").strip() or None
    return None


def _text(root: Any, path: str, namespaces: dict[str, str]) -> str | None:
    element = root.find(path, namespaces)
    if element is None or element.text is None:
        return None
    return element.text.strip() or None


def _decimal(root: Any, path: str, namespaces: dict[str, str]) -> Decimal | None:
    raw = _text(root, path, namespaces)
    if raw is None:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _cii_date(root: Any, path: str) -> date | None:
    """CII wraps its dates: `<DateTimeString format="102">20260131</...>`.

    Format 102 (`yyyymmdd`) is what the standard prescribes and what senders
    use; anything else is read as ISO before being given up on.
    """
    return _date(_text(root, f"{path}/udt:DateTimeString", CII_NS))


def _date(raw: str | None) -> date | None:
    if not raw:
        return None
    text = raw.strip()
    if len(text) == 8 and text.isdigit():
        try:
            return datetime.strptime(text, "%Y%m%d").date()
        except ValueError:
            return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None
