"""The look every document the club hands out shares.

Three renderers used to each carry their own margins, sizes and grey values,
which is how three documents from one club end up looking like three
documents from three clubs. This module owns those decisions once.

**It also owns the page.** The renderers hand over a list of flowables and
never touch a y-coordinate: reportlab's Platypus breaks the pages, repeats the
letterhead and the footer on every one of them, repeats a table header over a
long list and keeps blocks that belong together on one page. Counting
millimetres by hand — which is how this started — got the free document right
and quietly let the donation receipt run off the bottom.

Set in **Fira Sans**, embedded from `app/assets/fonts` (SIL Open Font License,
see the LICENSE there). Embedded rather than one of the PDF base-14 faces:
those are not carried inside the file, and what a reader without the real
Helvetica installed puts in its place is not ours to decide — for a document a
club prints and hands to an authority, the page should look the same
everywhere it is opened. reportlab subsets the font per document, so this
costs a few kilobytes a page.

The palette is monochrome because the app is: its tokens are all chroma 0, and
a document that arrives with a colour the product never uses reads as coming
from somewhere else. What carries the design instead is spacing, weight and
one hairline where a box would have been.
"""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

#: reportlab ships no type information, so its `mm` is untyped and every sum
#: built from it comes out as `Any`. Pinned to a float once, here.
mm: float = 72.0 / 25.4

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

REGULAR = "FiraSans"
MEDIUM = "FiraSans-Medium"
SEMIBOLD = "FiraSans-SemiBold"

_FILES = {
    REGULAR: "FiraSans-Regular.ttf",
    MEDIUM: "FiraSans-Medium.ttf",
    SEMIBOLD: "FiraSans-SemiBold.ttf",
}


def register_fonts() -> None:
    """Make Fira Sans available to reportlab. Safe to call repeatedly.

    Called at import so a missing or unreadable font file fails when the app
    starts rather than when a member asks for a certificate.
    """
    registered = set(pdfmetrics.getRegisteredFontNames())
    for name, filename in _FILES.items():
        if name not in registered:
            pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / filename)))


register_fonts()

#: Generous, so the page breathes. Everything sits inside it, footer included.
MARGIN = 24 * mm

# Greys, as fractions of white. Chosen to match the app's neutral tokens.
INK = 0.13
STRONG = 0.28
MUTED = 0.48
HAIRLINE = 0.82

#: Muted rather than a warning red — a revoked document should read as void,
#: not as an alarm.
REVOKED_COLOR = (0.62, 0.16, 0.16)
PASSED_COLOR = (0.10, 0.40, 0.20)

# Type scale. One step between sizes, no in-between values. Fira Sans has a
# larger x-height than Helvetica, so the same millimetres carry a smaller size.
TITLE = 18
SUBTITLE = 8.5
BODY = 10
LABEL = 6.8
SMALL = 8
FOOTNOTE = 7

BODY_LEADING = 15
#: Uppercase labels get letterspacing; at 7pt they are unreadable without it.
LABEL_TRACKING = 0.8

#: How much of the page the repeating furniture claims. The frame lives
#: between them, and Platypus never writes outside it.
MASTHEAD_BAND = 16 * mm
FOOTER_BAND = 12 * mm
#: With a QR the footer needs room for the code beside it.
FOOTER_BAND_WITH_CHECK = 30 * mm

BODY_STYLE = ParagraphStyle(
    "body", fontName=REGULAR, fontSize=BODY, leading=BODY_LEADING, textColor=(INK, INK, INK)
)
TITLE_STYLE = ParagraphStyle(
    "title",
    fontName=SEMIBOLD,
    fontSize=TITLE,
    leading=TITLE + 5,
    textColor=(INK, INK, INK),
    spaceAfter=2 * mm,
)
SUBTITLE_STYLE = ParagraphStyle(
    "subtitle",
    fontName=REGULAR,
    fontSize=SUBTITLE,
    leading=SUBTITLE + 3.5,
    textColor=(MUTED, MUTED, MUTED),
)
VALUE_STYLE = ParagraphStyle(
    "value", fontName=REGULAR, fontSize=BODY, leading=BODY + 2.5, textColor=(INK, INK, INK)
)
VALUE_STRONG_STYLE = ParagraphStyle(
    "valueStrong",
    fontName=MEDIUM,
    fontSize=BODY + 1.5,
    leading=BODY + 4,
    textColor=(INK, INK, INK),
)
TABLE_HEAD_STYLE = ParagraphStyle(
    "tableHead",
    fontName=MEDIUM,
    fontSize=LABEL,
    leading=LABEL + 2,
    textColor=(MUTED, MUTED, MUTED),
)
TABLE_CELL_STYLE = ParagraphStyle(
    "tableCell", fontName=REGULAR, fontSize=9, leading=12, textColor=(INK, INK, INK)
)
FOOTNOTE_STYLE = ParagraphStyle(
    "footnote",
    fontName=REGULAR,
    fontSize=FOOTNOTE,
    leading=FOOTNOTE + 2.6,
    textColor=(MUTED, MUTED, MUTED),
)


def text(value: str) -> str:
    """Escape club-authored text for a Paragraph.

    Paragraphs are parsed as XML, so a `&` in a club's name or a `<` in a
    document body would otherwise be a broken document rather than a printed
    character.
    """
    return escape(value)


def rich(value: str) -> str:
    """As `text`, but single newlines survive as line breaks.

    An address block is written with newlines and means them.
    """
    return escape(value).replace("\n", "<br/>")


def tracked(pdf: canvas.Canvas, x: float, y: float, value: str, spacing: float) -> None:
    """Draw text with letterspacing.

    Through a text object because that is where reportlab keeps character
    spacing — the canvas has no such setting, and the font and colour already
    set on the canvas carry over into it.

    Bracketed in `saveState`/`restoreState` because character spacing is part
    of the graphics state and **outlives the text object**. Left standing, it
    widened every later string on the page by 0.8pt per character while
    `stringWidth` — which is what right-aligned text anchors on — kept
    measuring them without it: the footer then ran off the right edge, and it
    looked convincingly like a font-substitution problem in the reader.
    """
    pdf.saveState()
    line = pdf.beginText(x, y)
    line.setCharSpace(spacing)
    line.textOut(value)
    pdf.drawText(line)
    pdf.restoreState()


@dataclass(frozen=True)
class Furniture:
    """What repeats on every page, and what the reader checks it against."""

    club_name: str
    #: Beside the club name — address, contact. Empty for no letterhead.
    address_lines: tuple[str, ...] = ()
    #: Register and tax data along the bottom. Empty when switched off.
    footer_lines: tuple[str, ...] = ()
    #: Both absent when the document is not verifiable — then no QR is drawn
    #: and nothing claims the document can be checked.
    verification_url: str | None = None
    verification_code: str | None = None

    @property
    def has_check(self) -> bool:
        return bool(self.verification_url and self.verification_code)


class _Label(Flowable):  # type: ignore[misc]  # reportlab ships no types
    """Small tracked capitals — a label, not a heading.

    Its own flowable because Platypus paragraphs have no letterspacing, and at
    this size capitals without it are a smudge.
    """

    def __init__(
        self,
        value: str,
        *,
        size: float = LABEL,
        font: str = MEDIUM,
        gray: float = MUTED,
        rule: bool = False,
    ) -> None:
        super().__init__()
        self.value = value.upper()
        self.size = size
        self.font = font
        self.gray = gray
        self.rule = rule
        self.width = 0.0
        self.height = size + (2.5 * mm if rule else 1.2 * mm)
        if rule:
            # More air above than below, so a section heading reads as
            # belonging to what follows it rather than floating between two
            # blocks. Platypus honours these around the flowable itself.
            self.spaceBefore = 5 * mm
            self.spaceAfter = 4.5 * mm

    def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
        self.width = available_width
        return self.width, self.height

    def draw(self) -> None:
        pdf = self.canv
        pdf.setFont(self.font, self.size)
        pdf.setFillGray(self.gray)
        tracked(pdf, 0, self.height - self.size, self.value, LABEL_TRACKING)
        if self.rule:
            pdf.setStrokeGray(HAIRLINE)
            pdf.setLineWidth(0.4)
            pdf.line(0, 0, self.width, 0)


class _Rule(Flowable):  # type: ignore[misc]  # reportlab ships no types
    """A signature line: something to sign above, a caption below."""

    def __init__(self, width: float, gray: float = 0.55) -> None:
        super().__init__()
        self.line_width = width
        self.gray = gray
        self.width = width
        self.height = 0.5

    def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
        return self.line_width, self.height

    def draw(self) -> None:
        self.canv.setStrokeGray(self.gray)
        self.canv.setLineWidth(0.5)
        self.canv.line(0, 0, self.line_width, 0)


def title(value: str, subtitle: str | None = None) -> list[Flowable]:
    """The document's own headline, and the sentence that qualifies it."""
    flowables: list[Flowable] = [Paragraph(text(value), TITLE_STYLE)]
    if subtitle:
        flowables.append(Paragraph(text(subtitle), SUBTITLE_STYLE))
    flowables.append(Spacer(0, 7 * mm))
    return flowables


def section(value: str) -> Flowable:
    """A tracked capital label over a hairline — the only kind of heading here."""
    return _Label(value, rule=True)


def facts(
    items: tuple[tuple[str, str], ...],
    *,
    columns: int = 2,
    emphasise: frozenset[str] = frozenset(),
) -> Flowable:
    """Label above value, in columns.

    Stacked rather than label-left/value-right across the whole page: at A4
    width that layout leaves a canyon between the two, and the eye has to
    travel it for every row.

    A real table, so a value that needs two lines makes its row taller instead
    of running into the label underneath it — which is what the hand-measured
    grid this replaces did.
    """
    rows: list[list[list[Flowable]]] = []
    for start in range(0, len(items), columns):
        row: list[list[Flowable]] = []
        for label, value in items[start : start + columns]:
            style = VALUE_STRONG_STYLE if label in emphasise else VALUE_STYLE
            row.append([_Label(label), Paragraph(text(value), style)])
        while len(row) < columns:
            row.append([])
        rows.append(row)

    usable = A4[0] - 2 * MARGIN
    gutter = 8 * mm
    column_width = (usable - gutter * (columns - 1)) / columns
    table = Table(
        rows,
        colWidths=[column_width + gutter] * (columns - 1) + [column_width],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), gutter),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6 * mm),
            ]
        )
    )
    return table


def paragraph(
    value: str, *, style: ParagraphStyle = BODY_STYLE, keep_breaks: bool = False
) -> Flowable:
    """One block of flowing text. `keep_breaks` for text a human typed."""
    return Paragraph(rich(value) if keep_breaks else text(value), style)


def signature(caption: str, width: float = 70 * mm) -> Flowable:
    """Line and caption, held together — a signature split over a page break
    would leave somebody signing a blank sheet."""
    return KeepTogether(
        [
            Spacer(0, 12 * mm),
            _Rule(width),
            Spacer(0, 1.5 * mm),
            Paragraph(text(caption), FOOTNOTE_STYLE),
        ]
    )


def verdict(value: str, color: tuple[float, float, float]) -> Flowable:
    """The one coloured line a document is allowed: its result."""
    red, green, blue = color
    style = ParagraphStyle(
        "verdict",
        fontName=MEDIUM,
        fontSize=BODY + 1.5,
        leading=BODY + 6,
        textColor=(red, green, blue),
    )
    return Paragraph(text(value), style)


def revoked_notice(value: str) -> Flowable:
    """Says the document is void, on its face.

    The check page is the second line of defence, not the first — somebody
    holding a printout should not have to scan a code to find out.
    """
    red, green, blue = REVOKED_COLOR
    style = ParagraphStyle(
        "revoked",
        fontName=MEDIUM,
        fontSize=SMALL + 0.5,
        leading=SMALL + 4,
        textColor=(red, green, blue),
    )
    table = Table([[Paragraph(text(value), style)]], colWidths=[A4[0] - 2 * MARGIN], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("LINEBEFORE", (0, 0), (0, -1), 1.2, (red, green, blue)),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6 * mm),
            ]
        )
    )
    return table


def _qr_drawing(url: str, size: float) -> Drawing:
    widget = qr.QrCodeWidget(url)
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
    return drawing


def _draw_furniture(
    pdf: canvas.Canvas, page_width: float, page_height: float, page: Furniture
) -> None:
    """Letterhead and footer, on every page.

    On every page rather than only the first: a second sheet that has come
    loose from the first should still say which club wrote it and how to check
    it.
    """
    pdf.saveState()

    top = page_height - MARGIN
    pdf.setFont(MEDIUM, LABEL)
    pdf.setFillGray(STRONG)
    tracked(pdf, MARGIN, top, page.club_name.upper(), LABEL_TRACKING)
    if page.address_lines:
        pdf.setFont(REGULAR, FOOTNOTE)
        pdf.setFillGray(MUTED)
        pdf.drawRightString(page_width - MARGIN, top, " · ".join(page.address_lines))
    pdf.setStrokeGray(HAIRLINE)
    pdf.setLineWidth(0.4)
    pdf.line(MARGIN, top - 4 * mm, page_width - MARGIN, top - 4 * mm)

    qr_size = 20 * mm if page.has_check else 0.0
    if page.has_check and page.verification_url:
        renderPDF.draw(_qr_drawing(page.verification_url, qr_size), pdf, MARGIN, MARGIN)

    if page.has_check or page.footer_lines:
        pdf.setStrokeGray(HAIRLINE)
        pdf.setLineWidth(0.4)
        rule_y = MARGIN + (qr_size or 6 * mm) + 6 * mm
        pdf.line(MARGIN, rule_y, page_width - MARGIN, rule_y)

    pdf.setFont(REGULAR, FOOTNOTE)
    pdf.setFillGray(MUTED)
    if page.footer_lines:
        pdf.drawRightString(page_width - MARGIN, MARGIN, " · ".join(page.footer_lines))
    if page.has_check:
        x = MARGIN + qr_size + 5 * mm
        y = MARGIN + qr_size - 3 * mm
        for line in (
            "Echtheit prüfen",
            page.verification_url or "",
            f"Prüfcode {page.verification_code}",
        ):
            pdf.drawString(x, y, line)
            y -= 3.6 * mm

    pdf.restoreState()


class _NumberedCanvas(canvas.Canvas):  # type: ignore[misc]  # reportlab ships no types
    """Holds the pages back so each one can say how many there are.

    "Seite 2" alone does not tell a reader whether a third page is missing,
    and the total is only known once the last page is laid out. A single page
    gets no number at all — it would be noise.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._pages: list[dict[str, Any]] = []

    def showPage(self) -> None:  # noqa: N802 — reportlab's name
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._pages)
        for number, state in enumerate(self._pages, start=1):
            self.__dict__.update(state)
            if total > 1:
                self.setFont(REGULAR, FOOTNOTE)
                self.setFillGray(MUTED)
                self.drawRightString(A4[0] - MARGIN, MARGIN + 5 * mm, f"Seite {number} von {total}")
            super().showPage()
        super().save()


def build(story: list[Flowable], *, page: Furniture, pdf_title: str) -> bytes:
    """Lay the flowables out over as many pages as they need, and return bytes.

    Every renderer in this package ends here. None of them decides where a
    page ends.
    """
    buffer = BytesIO()
    width, height = A4
    footer_band = FOOTER_BAND_WITH_CHECK if page.has_check or page.footer_lines else FOOTER_BAND

    document = BaseDocTemplate(
        buffer,
        pagesize=A4,
        title=pdf_title,
        # Not a claim about the club, only about who produced the file.
        author=page.club_name,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN + MASTHEAD_BAND,
        bottomMargin=MARGIN + footer_band,
    )
    frame = Frame(
        MARGIN,
        MARGIN + footer_band,
        width - 2 * MARGIN,
        height - MARGIN - MASTHEAD_BAND - MARGIN - footer_band,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    document.addPageTemplates(
        [
            PageTemplate(
                id="page",
                frames=[frame],
                onPage=lambda pdf, _doc: _draw_furniture(pdf, width, height, page),
            )
        ]
    )
    document.build(story, canvasmaker=_NumberedCanvas)
    return buffer.getvalue()
