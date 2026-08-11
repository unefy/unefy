"""The printable donation receipt.

Follows the structure of the official template published by the German tax
administration: who issued it, who gave, how much in figures and in words,
when, what kind of contribution, which notice recognises the club, and the
liability notice. Every line here is on the page because the template puts it
there — this is the one document in the product where wording is not the
club's to choose.

**Check the wording against the current official template before productive
use.** The texts are collected in `TEXTS` for exactly that reason: updating
them is one obvious edit in one place, not a hunt through a renderer.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.services.amount_in_words import euros_in_words

MARGIN = 20 * mm
LEADING = 4.8 * mm

#: The prescribed sentences, in one place so they can be checked and updated
#: against the current official template without reading the renderer.
TEXTS = {
    "title": "Bestätigung über Geldzuwendungen",
    "subtitle": (
        "im Sinne des § 10b des Einkommensteuergesetzes an eine der in § 5 Abs. 1 "
        "Nr. 9 des Körperschaftsteuergesetzes bezeichneten Körperschaften, "
        "Personenvereinigungen oder Vermögensmassen"
    ),
    "waiver_question": "Es handelt sich um den Verzicht auf Erstattung von Aufwendungen:",
    "purpose_intro": (
        "Wir sind wegen Förderung folgender Zwecke nach dem Freistellungsbescheid "
        "bzw. der Anlage zum Körperschaftsteuerbescheid des Finanzamts"
    ),
    "exemption_60a": (
        "Wir sind wegen Förderung folgender Zwecke durch vorläufige Bescheinigung "
        "bzw. Feststellung nach § 60a AO des Finanzamts"
    ),
    "usage": (
        "Es wird bestätigt, dass die Zuwendung nur zur Förderung der vorstehend "
        "genannten Zwecke verwendet wird."
    ),
    "liability": (
        "Wer vorsätzlich oder grob fahrlässig eine unrichtige Zuwendungsbestätigung "
        "erstellt oder wer veranlasst, dass Zuwendungen nicht zu den in der "
        "Zuwendungsbestätigung angegebenen steuerbegünstigten Zwecken verwendet "
        "werden, haftet für die entgangene Steuer (§ 10b Abs. 4 EStG, § 9 Abs. 3 "
        "KStG, § 9 Nr. 5 GewStG)."
    ),
    "signature": "Ort, Datum und Unterschrift des Zuwendungsempfängers",
    "revoked": "WIDERRUFEN — diese Bestätigung ist ungültig",
}


@dataclass(frozen=True)
class DonationDocument:
    """Everything the page prints, already resolved."""

    club_name: str
    club_address: str | None
    donor_name: str
    donor_address: str | None
    amount: Decimal
    received_on: date
    #: "geldzuwendung" | "mitgliedsbeitrag"
    kind: str
    is_expense_waiver: bool
    #: "freistellungsbescheid" | "feststellung_60a"
    exemption_kind: str
    exemption_date: date
    exemption_period: int | None
    tax_office: str
    tax_number: str
    purposes: str
    issued_on: date
    verification_code: str
    verification_url: str
    revoked: bool = False


def _de(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _money(value: Decimal) -> str:
    return f"{value:,.2f} EUR".replace(",", "#").replace(".", ",").replace("#", ".")


def _wrap(pdf: canvas.Canvas, text: str, width: float, font: str, size: float) -> list[str]:
    """Greedy word wrap against the real string widths of the chosen font."""
    if not text:
        return [""]

    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = f"{current} {word}".strip()
        if current and pdf.stringWidth(candidate, font, size) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    lines.append(current)
    return lines


def build_donation_pdf(doc: DonationDocument) -> bytes:
    """Render one donation receipt to PDF bytes."""
    buffer = BytesIO()
    width, height = A4
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"{TEXTS['title']} — {doc.donor_name}")
    pdf.setAuthor(doc.club_name)

    text_width = width - 2 * MARGIN
    y = height - MARGIN

    def paragraph(text: str, size: float = 9, font: str = "Helvetica", gap: float = 2 * mm) -> None:
        nonlocal y
        pdf.setFont(font, size)
        for line in _wrap(pdf, text, text_width, font, size):
            pdf.drawString(MARGIN, y, line)
            y -= LEADING
        y -= gap

    # Issuer block — the template puts the recipient of the donation first.
    pdf.setFont("Helvetica", 8)
    pdf.setFillGray(0.35)
    pdf.drawString(MARGIN, y, "Aussteller (Zuwendungsempfänger)")
    pdf.setFillGray(0)
    y -= LEADING
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(MARGIN, y, doc.club_name)
    y -= LEADING
    if doc.club_address:
        pdf.setFont("Helvetica", 9)
        pdf.drawString(MARGIN, y, doc.club_address)
        y -= LEADING
    y -= 6 * mm

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(MARGIN, y, TEXTS["title"])
    y -= 6 * mm
    paragraph(TEXTS["subtitle"], size=8, gap=5 * mm)

    pdf.setLineWidth(0.5)
    pdf.setStrokeGray(0.8)
    pdf.line(MARGIN, y, width - MARGIN, y)
    y -= 8 * mm

    # Donor.
    pdf.setFont("Helvetica", 8)
    pdf.setFillGray(0.35)
    pdf.drawString(MARGIN, y, "Name und Anschrift des Zuwendenden")
    pdf.setFillGray(0)
    y -= LEADING
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(MARGIN, y, doc.donor_name)
    y -= LEADING
    if doc.donor_address:
        pdf.setFont("Helvetica", 9)
        pdf.drawString(MARGIN, y, doc.donor_address)
        y -= LEADING
    y -= 6 * mm

    # The amount, twice: a figure can be altered with a pen and a word cannot.
    y = _fact(pdf, y, "Betrag der Zuwendung — in Ziffern", _money(doc.amount), bold=True)
    y = _fact(pdf, y, "in Buchstaben", euros_in_words(doc.amount))
    y = _fact(pdf, y, "Tag der Zuwendung", _de(doc.received_on))
    y = _fact(
        pdf,
        y,
        "Art der Zuwendung",
        "Mitgliedsbeitrag" if doc.kind == "mitgliedsbeitrag" else "Geldzuwendung",
    )
    # Printed either way: a blank box is an unanswered question, not a "no".
    y = _fact(pdf, y, TEXTS["waiver_question"], "Ja" if doc.is_expense_waiver else "Nein")
    y -= 4 * mm

    # Which notice recognises the club, and for what.
    if doc.exemption_kind == "feststellung_60a":
        recognition = (
            f"{TEXTS['exemption_60a']} {doc.tax_office}, StNr. {doc.tax_number}, "
            f"vom {_de(doc.exemption_date)} als steuerbegünstigten Zwecken dienend "
            f"anerkannt: {doc.purposes}."
        )
    else:
        period = (
            f" für den letzten Veranlagungszeitraum {doc.exemption_period}"
            if doc.exemption_period
            else ""
        )
        recognition = (
            f"{TEXTS['purpose_intro']} {doc.tax_office}, StNr. {doc.tax_number}, "
            f"vom {_de(doc.exemption_date)}{period} nach § 5 Abs. 1 Nr. 9 KStG von der "
            f"Körperschaftsteuer befreit: {doc.purposes}."
        )
    paragraph(recognition, gap=3 * mm)
    paragraph(TEXTS["usage"], gap=6 * mm)

    # Signature line — a receipt is signed by a person, not by a server.
    pdf.setStrokeGray(0.6)
    pdf.line(MARGIN, y, MARGIN + 80 * mm, y)
    y -= 4 * mm
    pdf.setFont("Helvetica", 8)
    pdf.setFillGray(0.35)
    pdf.drawString(MARGIN, y, TEXTS["signature"])
    pdf.setFillGray(0)
    y -= 8 * mm

    paragraph(TEXTS["liability"], size=7.5, gap=4 * mm)

    if doc.revoked:
        # On its face, not only on the check page — the page is the second
        # line of defence, not the first.
        pdf.setFillColorRGB(0.7, 0.1, 0.1)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(MARGIN, y, TEXTS["revoked"])
        pdf.setFillGray(0)
        y -= 6 * mm

    _draw_check(pdf, doc)

    pdf.save()
    return buffer.getvalue()


def _fact(pdf: canvas.Canvas, y: float, label: str, value: str, *, bold: bool = False) -> float:
    pdf.setFont("Helvetica", 8)
    pdf.setFillGray(0.35)
    pdf.drawString(MARGIN, y, label)
    pdf.setFillGray(0)
    pdf.setFont("Helvetica-Bold" if bold else "Helvetica", 11 if bold else 10)
    pdf.drawString(MARGIN + 70 * mm, y, value)
    return float(y - 7 * mm)


def _draw_check(pdf: canvas.Canvas, doc: DonationDocument) -> None:
    """QR and check code, pinned to the bottom.

    Not part of the prescribed form, and deliberately set apart from it: it
    says nothing about the tax treatment, only that this piece of paper came
    from this club.
    """
    widget = qr.QrCodeWidget(doc.verification_url)
    bounds = widget.getBounds()
    size = 22 * mm
    drawing = Drawing(
        size,
        size,
        transform=[
            size / (bounds[2] - bounds[0]),
            0,
            0,
            size / (bounds[3] - bounds[1]),
            0,
            0,
        ],
    )
    drawing.add(widget)
    renderPDF.draw(drawing, pdf, MARGIN, MARGIN)

    pdf.setFont("Helvetica", 7.5)
    pdf.setFillGray(0.4)
    pdf.drawString(MARGIN + size + 4 * mm, MARGIN + 16 * mm, "Echtheit prüfen:")
    pdf.drawString(MARGIN + size + 4 * mm, MARGIN + 12 * mm, doc.verification_url)
    pdf.drawString(MARGIN + size + 4 * mm, MARGIN + 8 * mm, f"Prüfcode: {doc.verification_code}")
    pdf.drawString(MARGIN + size + 4 * mm, MARGIN + 4 * mm, f"Ausgestellt am {_de(doc.issued_on)}")
    pdf.setFillGray(0)
