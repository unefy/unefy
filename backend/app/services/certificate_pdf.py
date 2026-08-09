"""The printable §14 certificate.

A club hands this to an authority, so it has to be a document rather than a
screenshot: one page, the numbers it rests on, and a way to check it against
the issuing server. That last part is the QR — it points at the *web app's*
public check page, not at the API, because whoever scans it is holding a piece
of paper and expects a page, not JSON.

Drawn rather than templated: one page of fixed structure is less code this way
than a template engine plus a HTML-to-PDF converter, and it adds no runtime
that has to be kept patched.
"""

from dataclasses import dataclass
from datetime import date
from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

#: Everything sits inside this margin, including the footer.
MARGIN = 22 * mm

TITLE = "Nachweis über regelmäßiges Schießen"
SUBTITLE = "gemäß § 14 Absatz 2 und 3 Waffengesetz"


@dataclass(frozen=True)
class CertificateDocument:
    """Everything the page prints, already resolved and formatted-agnostic."""

    club_name: str
    member_name: str
    member_number: str | None
    rule_label: str
    period_start: date
    period_end: date
    session_count: int
    months_covered: int
    self_certified_days: int
    external_days: int
    passed: bool
    issued_on: date
    verification_code: str
    #: Where the QR points. Built by the caller, which knows the app's URL.
    verification_url: str
    revoked: bool = False


def _de(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _line(pdf: canvas.Canvas, y: float, label: str, value: str) -> float:
    """One label/value row, returning the next baseline."""
    pdf.setFont("Helvetica", 10)
    pdf.setFillGray(0.35)
    pdf.drawString(MARGIN, y, label)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.setFillGray(0)
    pdf.drawString(MARGIN + 62 * mm, y, value)
    return y - 8 * mm


def build_certificate_pdf(doc: CertificateDocument) -> bytes:
    """Render one certificate to PDF bytes."""
    buffer = BytesIO()
    width, height = A4
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"{TITLE} — {doc.member_name}")
    # Not a claim about the club, only about who produced the file.
    pdf.setAuthor(doc.club_name)

    y = height - MARGIN

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(MARGIN, y, doc.club_name)
    y -= 14 * mm

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(MARGIN, y, TITLE)
    y -= 6 * mm
    pdf.setFont("Helvetica", 10)
    pdf.setFillGray(0.35)
    pdf.drawString(MARGIN, y, SUBTITLE)
    pdf.setFillGray(0)
    y -= 12 * mm

    pdf.setLineWidth(0.5)
    pdf.setStrokeGray(0.8)
    pdf.line(MARGIN, y, width - MARGIN, y)
    y -= 12 * mm

    member = doc.member_name
    if doc.member_number:
        member = f"{member} (Mitglied {doc.member_number})"
    y = _line(pdf, y, "Mitglied", member)
    y = _line(pdf, y, "Zeitraum", f"{_de(doc.period_start)} bis {_de(doc.period_end)}")
    y = _line(pdf, y, "Schießtage", str(doc.session_count))
    y = _line(pdf, y, "Monate mit Terminen", str(doc.months_covered))
    y = _line(pdf, y, "Zugrunde liegende Regel", doc.rule_label)

    # Named rather than folded into the total: a day that rests on the member's
    # own word is not the same evidence as one a supervisor attested, and a
    # certificate that hides the difference is worth less, not more.
    if doc.self_certified_days or doc.external_days:
        y = _line(
            pdf,
            y,
            "davon selbst geführt",
            f"{doc.self_certified_days} (fremde Stände: {doc.external_days})",
        )

    y -= 4 * mm
    pdf.setFont("Helvetica-Bold", 13)
    if doc.revoked:
        pdf.setFillColorRGB(0.7, 0.1, 0.1)
        pdf.drawString(MARGIN, y, "Diese Bescheinigung wurde widerrufen.")
    elif doc.passed:
        pdf.setFillColorRGB(0.1, 0.45, 0.2)
        pdf.drawString(MARGIN, y, "Die Voraussetzungen der Regel sind erfüllt.")
    else:
        pdf.setFillColorRGB(0.7, 0.1, 0.1)
        pdf.drawString(MARGIN, y, "Die Voraussetzungen der Regel sind nicht erfüllt.")
    pdf.setFillGray(0)
    y -= 16 * mm

    # The QR and the code say the same thing twice on purpose: a scanner is
    # quicker, but a code that can be typed still works from a photocopy.
    widget = qr.QrCodeWidget(doc.verification_url)
    bounds = widget.getBounds()
    size = 32 * mm
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
    renderPDF.draw(drawing, pdf, MARGIN, y - size)

    text_x = MARGIN + size + 8 * mm
    pdf.setFont("Helvetica", 10)
    pdf.setFillGray(0.35)
    pdf.drawString(text_x, y - 6 * mm, "Echtheit prüfen:")
    pdf.setFillGray(0)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(text_x, y - 12 * mm, doc.verification_url)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(text_x, y - 20 * mm, f"Prüfcode: {doc.verification_code}")

    pdf.setFont("Helvetica", 9)
    pdf.setFillGray(0.35)
    pdf.drawString(
        MARGIN,
        MARGIN,
        f"Ausgestellt am {_de(doc.issued_on)} · "
        "Die Prüfseite bestätigt Gültigkeit, Zeitraum und Anzahl der Schießtage.",
    )

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
