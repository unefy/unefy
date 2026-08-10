"""The printable free-form document: letterhead, the club's text, a QR.

The counterpart to `certificate_pdf`. That one draws a prescribed form and
knows every field it prints. This one knows nothing about the content — the
club wrote it — and only has to place flowing text on a page and break it
where it runs out.

Drawn rather than templated, for the same reason as the other: one page of
fixed structure is less code than a template engine plus an HTML converter,
and it adds no runtime that has to be kept patched.
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
BODY_SIZE = 11
BODY_LEADING = 5.6 * mm
#: Space between paragraphs, on top of the line leading.
PARAGRAPH_GAP = 3 * mm


@dataclass(frozen=True)
class DocumentLetter:
    """Everything the page prints, already rendered and resolved."""

    club_name: str
    title: str
    #: The rendered text. Blank lines separate paragraphs; single newlines are
    #: kept as line breaks, because an address block is written that way.
    body: str
    issued_on: date

    #: Letterhead lines under the club name — address, contact. Empty when the
    #: template asked for no letterhead.
    letterhead: tuple[str, ...] = ()
    #: Register and tax data along the bottom. Empty when switched off.
    footer: tuple[str, ...] = ()

    #: Absent when the template is not verifiable — then no QR is drawn and
    #: nothing claims the document can be checked.
    verification_code: str | None = None
    verification_url: str | None = None
    revoked: bool = False

    #: Caption under a ruled line the club signs by hand.
    signature_line: str | None = None


def _de(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _wrap(pdf: canvas.Canvas, text: str, width: float, font: str, size: float) -> list[str]:
    """Greedy word wrap against the real string widths of the chosen font.

    Measured rather than estimated by character count: "Mitgliedsbescheinigung"
    and "iiiiiiiiiiiiiiiiiiiiii" have the same length and nothing else.
    """
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


def build_document_pdf(doc: DocumentLetter) -> bytes:
    """Render one document to PDF bytes, over as many pages as it needs.

    The club writes the text, so the length is not ours to bound. Running onto
    a second page is normal here, unlike the §14 certificate.
    """
    buffer = BytesIO()
    width, height = A4
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(doc.title)
    # Not a claim about the club, only about who produced the file.
    pdf.setAuthor(doc.club_name)

    text_width = width - 2 * MARGIN
    # Where the text may not go, so the footer and QR keep their room.
    floor = MARGIN + (34 * mm if doc.footer or doc.verification_code else 8 * mm)

    def new_page() -> float:
        pdf.showPage()
        pdf.setFillGray(0)
        return float(height - MARGIN)

    y = float(height - MARGIN)

    if doc.letterhead or doc.club_name:
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(MARGIN, y, doc.club_name)
        y -= 6 * mm
        pdf.setFont("Helvetica", 9)
        pdf.setFillGray(0.35)
        for line in doc.letterhead:
            pdf.drawString(MARGIN, y, line)
            y -= 4.5 * mm
        pdf.setFillGray(0)
        y -= 6 * mm

    pdf.setFont("Helvetica-Bold", 16)
    for line in _wrap(pdf, doc.title, text_width, "Helvetica-Bold", 16):
        pdf.drawString(MARGIN, y, line)
        y -= 7 * mm
    y -= 4 * mm

    pdf.setLineWidth(0.5)
    pdf.setStrokeGray(0.8)
    pdf.line(MARGIN, y, width - MARGIN, y)
    y -= 10 * mm

    pdf.setFont("Helvetica", BODY_SIZE)
    for paragraph in doc.body.split("\n\n"):
        for source_line in paragraph.split("\n"):
            for line in _wrap(pdf, source_line, text_width, "Helvetica", BODY_SIZE):
                if y < floor:
                    y = new_page()
                    pdf.setFont("Helvetica", BODY_SIZE)
                pdf.drawString(MARGIN, y, line)
                y -= BODY_LEADING
        y -= PARAGRAPH_GAP

    if doc.signature_line:
        y -= 12 * mm
        if y < floor:
            y = new_page()
        pdf.setStrokeGray(0.6)
        pdf.line(MARGIN, y, MARGIN + 60 * mm, y)
        y -= 5 * mm
        pdf.setFont("Helvetica", 9)
        pdf.setFillGray(0.35)
        pdf.drawString(MARGIN, y, doc.signature_line)
        pdf.setFillGray(0)

    _draw_foot(pdf, doc, width)

    pdf.save()
    return buffer.getvalue()


def _draw_foot(pdf: canvas.Canvas, doc: DocumentLetter, width: float) -> None:
    """QR, check code and register data, pinned to the bottom of the last page.

    Pinned rather than following the text: a reader looking for the check code
    should find it in the same place on every document a club issues.
    """
    if doc.verification_code and doc.verification_url:
        # The QR and the code say the same thing twice on purpose: a scanner is
        # quicker, but a code that can be typed still works from a photocopy.
        widget = qr.QrCodeWidget(doc.verification_url)
        bounds = widget.getBounds()
        size = 24 * mm
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
        renderPDF.draw(drawing, pdf, MARGIN, MARGIN + 6 * mm)

        pdf.setFont("Helvetica", 8)
        pdf.setFillGray(0.35)
        pdf.drawString(
            MARGIN + size + 4 * mm,
            MARGIN + 22 * mm,
            f"Echtheit prüfen: {doc.verification_url}",
        )
        pdf.drawString(
            MARGIN + size + 4 * mm, MARGIN + 18 * mm, f"Prüfcode: {doc.verification_code}"
        )
        pdf.drawString(
            MARGIN + size + 4 * mm,
            MARGIN + 14 * mm,
            f"Ausgestellt am {_de(doc.issued_on)}",
        )
        if doc.revoked:
            # A revoked document should say so on its face, not only on the
            # check page — the page is the second line of defence, not the
            # first.
            pdf.setFillColorRGB(0.7, 0.1, 0.1)
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(MARGIN + size + 4 * mm, MARGIN + 9 * mm, "WIDERRUFEN — ungültig")
        pdf.setFillGray(0.35)

    if doc.footer:
        pdf.setFont("Helvetica", 7.5)
        pdf.setFillGray(0.45)
        y = MARGIN + 2 * mm
        pdf.drawRightString(width - MARGIN, y, " · ".join(doc.footer))
        pdf.setFillGray(0)
