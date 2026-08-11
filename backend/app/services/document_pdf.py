"""The printable free-form document: letterhead, the club's text, a QR.

The counterpart to `certificate_pdf`. That one draws a prescribed form and
knows every field it prints. This one knows nothing about the content — the
club wrote it — and only has to place flowing text on a page and break it
where it runs out.

How it looks is `pdf_theme`'s business, shared with the other documents.
"""

from dataclasses import dataclass
from datetime import date
from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.services import pdf_theme as theme
from app.services.pdf_theme import mm

BODY_SIZE = theme.BODY
BODY_LEADING = theme.BODY_LEADING
#: Space between paragraphs, on top of the line leading.
PARAGRAPH_GAP = 3 * mm

REVOKED_TEXT = "WIDERRUFEN — dieses Dokument ist ungültig"


@dataclass(frozen=True)
class DocumentLetter:
    """Everything the page prints, already rendered and resolved."""

    club_name: str
    title: str
    #: The rendered text. Blank lines separate paragraphs; single newlines are
    #: kept as line breaks, because an address block is written that way.
    body: str
    issued_on: date

    #: Letterhead lines beside the club name — address, contact. Empty when the
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

    text_width = width - 2 * theme.MARGIN
    # Where the text may not go, so the footer and QR keep their room.
    floor = theme.MARGIN + (32 * mm if doc.footer or doc.verification_code else 12 * mm)

    def new_page() -> float:
        pdf.showPage()
        pdf.setFillGray(theme.INK)
        return float(height - theme.MARGIN)

    y = theme.masthead(
        pdf,
        width,
        height - theme.MARGIN,
        club_name=doc.club_name,
        address_lines=doc.letterhead,
    )
    y = theme.title(pdf, width, y, text=doc.title)

    if doc.revoked:
        y = theme.revoked_notice(pdf, width, y, REVOKED_TEXT)

    pdf.setFont("Helvetica", BODY_SIZE)
    for paragraph in doc.body.split("\n\n"):
        for source_line in paragraph.split("\n"):
            for line in theme.wrap(pdf, source_line, text_width, "Helvetica", BODY_SIZE):
                if y < floor:
                    y = new_page()
                    pdf.setFont("Helvetica", BODY_SIZE)
                pdf.drawString(theme.MARGIN, y, line)
                y -= BODY_LEADING
        y -= PARAGRAPH_GAP

    if doc.signature_line:
        y -= 12 * mm
        if y < floor:
            y = new_page()
        theme.signature_line(pdf, y, doc.signature_line)

    _draw_foot(pdf, doc, width)

    pdf.save()
    return buffer.getvalue()


def _draw_foot(pdf: canvas.Canvas, doc: DocumentLetter, width: float) -> None:
    """QR, check code and register data, pinned to the bottom of the last page.

    Pinned rather than following the text: a reader looking for the check code
    should find it in the same place on every document a club issues.
    """
    size = 0.0
    if doc.verification_code and doc.verification_url:
        # The QR and the code say the same thing twice on purpose: a scanner is
        # quicker, but a code that can be typed still works from a photocopy.
        size = 20 * mm
        widget = qr.QrCodeWidget(doc.verification_url)
        bounds = widget.getBounds()
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
        renderPDF.draw(drawing, pdf, theme.MARGIN, theme.MARGIN)

    if size or doc.footer:
        theme.footer_rule(pdf, width, theme.MARGIN + (size or 6 * mm) + 6 * mm)

    theme.footer(
        pdf,
        width,
        lines=(*doc.footer, f"Ausgestellt am {_de(doc.issued_on)}"),
        check_lines=(
            (
                "Echtheit prüfen",
                doc.verification_url or "",
                f"Prüfcode {doc.verification_code}",
            )
            if doc.verification_code
            else ()
        ),
        qr_size=size,
    )
