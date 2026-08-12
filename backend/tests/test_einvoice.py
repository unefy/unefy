"""Reading a structured e-invoice, and refusing to guess when it is not one."""

import io
from datetime import date
from decimal import Decimal

from app.services.einvoice import parse

# A ZUGFeRD/Factur-X invoice in UN/CEFACT CII, cut down to the fields a
# register reads. The namespaces and the wrapped date are exactly as senders
# write them — that shape is the reason the parser exists.
CII_TEXT = """<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
    xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocument>
    <ram:ID>RE-2026-0815</ram:ID>
    <ram:IssueDateTime>
      <udt:DateTimeString format="102">20260131</udt:DateTimeString>
    </ram:IssueDateTime>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty>
        <ram:Name>Sportgeräte Müller GmbH</ram:Name>
        <ram:SpecifiedTaxRegistration>
          <ram:ID schemeID="FC">12/345/67890</ram:ID>
        </ram:SpecifiedTaxRegistration>
        <ram:SpecifiedTaxRegistration>
          <ram:ID schemeID="VA">DE123456789</ram:ID>
        </ram:SpecifiedTaxRegistration>
      </ram:SellerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
      <ram:SpecifiedTradePaymentTerms>
        <ram:DueDateDateTime>
          <udt:DateTimeString format="102">20260214</udt:DateTimeString>
        </ram:DueDateDateTime>
      </ram:SpecifiedTradePaymentTerms>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:TaxBasisTotalAmount>420.00</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount currencyID="EUR">79.80</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>499.80</ram:GrandTotalAmount>
        <ram:DuePayableAmount>499.80</ram:DuePayableAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>
"""

#: Encoded once. A byte literal cannot hold an umlaut, and a supplier called
#: "Sportgeräte Müller" is the normal case in this country, not the edge one.
CII = CII_TEXT.encode("utf-8")

UBL_TEXT = """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ID>2026-0042</cbc:ID>
  <cbc:IssueDate>2026-03-01</cbc:IssueDate>
  <cbc:DueDate>2026-03-15</cbc:DueDate>
  <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyName><cbc:Name>Vereinsbedarf Schmitt</cbc:Name></cac:PartyName>
      <cac:PartyTaxScheme><cbc:CompanyID>DE987654321</cbc:CompanyID></cac:PartyTaxScheme>
      <cac:PartyLegalEntity>
        <cbc:RegistrationName>Vereinsbedarf Schmitt e.K.</cbc:RegistrationName>
      </cac:PartyLegalEntity>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:TaxTotal><cbc:TaxAmount currencyID="EUR">19.00</cbc:TaxAmount></cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:TaxExclusiveAmount currencyID="EUR">100.00</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="EUR">119.00</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="EUR">119.00</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
</Invoice>
"""

UBL = UBL_TEXT.encode("utf-8")


def test_a_zugferd_invoice_is_read_field_by_field() -> None:
    parsed = parse(CII, "application/xml")

    assert parsed is not None
    assert parsed.source == "xrechnung"  # bare XML, whatever syntax it is in
    assert parsed.invoice_number == "RE-2026-0815"
    assert parsed.invoice_date == date(2026, 1, 31)
    assert parsed.due_date == date(2026, 2, 14)
    assert parsed.supplier_name == "Sportgeräte Müller GmbH"
    assert parsed.net_amount == Decimal("420.00")
    assert parsed.tax_amount == Decimal("79.80")
    assert parsed.gross_amount == Decimal("499.80")
    assert parsed.currency == "EUR"


def test_the_vat_number_is_taken_and_the_tax_number_left() -> None:
    """A seller carries both. Only one of them identifies them anywhere."""
    parsed = parse(CII, "application/xml")

    assert parsed is not None
    assert parsed.supplier_vat_id == "DE123456789"


def test_an_xrechnung_in_ubl_is_read_too() -> None:
    """XRechnung is a profile, not a syntax — it arrives as UBL or as CII."""
    parsed = parse(UBL, "application/xml")

    assert parsed is not None
    assert parsed.invoice_number == "2026-0042"
    assert parsed.invoice_date == date(2026, 3, 1)
    assert parsed.due_date == date(2026, 3, 15)
    # The legal name wins over the trading name: it is what the club owes.
    assert parsed.supplier_name == "Vereinsbedarf Schmitt e.K."
    assert parsed.supplier_vat_id == "DE987654321"
    assert parsed.gross_amount == Decimal("119.00")


def test_what_is_still_owed_beats_the_invoice_total() -> None:
    """After a prepayment the two differ, and the club owes the smaller one."""
    with_prepayment = CII_TEXT.replace(
        "<ram:DuePayableAmount>499.80</ram:DuePayableAmount>",
        "<ram:DuePayableAmount>299.80</ram:DuePayableAmount>",
    )
    parsed = parse(with_prepayment.encode("utf-8"), "application/xml")

    assert parsed is not None
    assert parsed.gross_amount == Decimal("299.80")


def test_a_missing_field_is_missing_and_not_zero() -> None:
    """A sender may leave out a due date; a parser that filled in one would
    invent a deadline the club then chases."""
    without_terms = CII_TEXT.replace("20260214", "")
    parsed = parse(without_terms.encode("utf-8"), "application/xml")

    assert parsed is not None
    assert parsed.due_date is None
    assert parsed.gross_amount == Decimal("499.80")


def zugferd_pdf(attachment_name: str = "factur-x.xml") -> bytes:
    """A PDF with the invoice XML attached — what actually lands in the inbox.

    Built rather than committed as a fixture: a binary blob in the repository
    would be unreadable, and this way the test states exactly what makes the
    file a ZUGFeRD invoice — a PDF a person can read, with the same invoice
    attached as data.
    """
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.add_attachment(attachment_name, CII)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_the_xml_inside_a_pdf_is_what_gets_read() -> None:
    """The normal case: the club receives one file that is both at once."""
    parsed = parse(zugferd_pdf(), "application/pdf")

    assert parsed is not None
    assert parsed.source == "zugferd"
    assert parsed.invoice_number == "RE-2026-0815"
    assert parsed.gross_amount == Decimal("499.80")
    assert parsed.supplier_name == "Sportgeräte Müller GmbH"


def test_an_attachment_under_an_unexpected_name_is_still_tried() -> None:
    """Senders have disagreed about the filename since ZUGFeRD 1.0. An
    attachment that parses as an invoice beats a filename that does not."""
    parsed = parse(zugferd_pdf("Rechnung_2026_0815.xml"), "application/pdf")

    assert parsed is not None
    assert parsed.invoice_number == "RE-2026-0815"


def test_a_pdf_without_an_attachment_is_a_scan() -> None:
    """A plain PDF is not a failure — it is the other half of the feature."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    buffer = io.BytesIO()
    writer.write(buffer)

    assert parse(buffer.getvalue(), "application/pdf") is None


def test_something_that_is_not_an_invoice_yields_nothing() -> None:
    """And never raises: the upload keeps the file and a person fills it in."""
    assert parse(b"%PDF-1.7\nnot really a pdf", "application/pdf") is None
    assert parse(b"<html><body>Rechnung</body></html>", "text/html") is None
    assert parse(b"scan of a paper invoice", "image/jpeg") is None
    assert parse(b"", "application/pdf") is None


def test_a_malformed_e_invoice_yields_nothing_rather_than_failing() -> None:
    assert parse(CII[: len(CII) // 2], "application/xml") is None


def test_the_billion_laughs_does_not_get_a_laugh() -> None:
    """An entity bomb in an uploaded file must not take the server with it.

    This is why the parser uses defusedxml rather than the standard library's
    ElementTree: the file comes from outside, and the club cannot vet it.
    """
    bomb = b"""<?xml version="1.0"?>
    <!DOCTYPE lolz [
      <!ENTITY lol "lol">
      <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
      <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
    ]>
    <Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">&lol3;</Invoice>
    """
    assert parse(bomb, "application/xml") is None
