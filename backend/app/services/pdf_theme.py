"""The look every document the club hands out shares.

Three renderers used to each carry their own margins, sizes and grey values,
which is how three documents from one club end up looking like three
documents from three clubs. This module owns those decisions once.

The palette is monochrome because the app is: its tokens are all chroma 0, and
a document that arrives with a colour the product never uses reads as coming
from somewhere else. What carries the design instead is spacing, weight and
one hairline where a box would have been.

Helvetica throughout — a PDF base-14 font. Embedding a nicer face is possible
and deliberately not done: it would put a binary in the repository and in the
image for a difference that a letter-sized block of text mostly hides, and the
base-14 fonts render identically on every reader and printer.
"""

from reportlab.lib.units import mm as _mm
from reportlab.pdfgen import canvas

#: reportlab ships no type information, so its `mm` is untyped and every sum
#: built from it comes out as `Any`. Pinned to a float once, here.
mm: float = float(_mm)

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

# Type scale. One step between sizes, no in-between values.
TITLE = 19
SUBTITLE = 8.5
HEADING = 10.5
BODY = 10.5
LABEL = 7
SMALL = 8
FOOTNOTE = 7

BODY_LEADING = 5.4 * mm
#: Uppercase labels get letterspacing; at 7pt they are unreadable without it.
LABEL_TRACKING = 0.7


def tracked(pdf: canvas.Canvas, x: float, y: float, text: str, spacing: float) -> None:
    """Draw text with letterspacing.

    Through a text object because that is where reportlab keeps character
    spacing — the canvas has no such setting, and the font and colour already
    set on the canvas carry over into it.
    """
    line = pdf.beginText(x, y)
    line.setCharSpace(spacing)
    line.textOut(text)
    pdf.drawText(line)


def wrap(pdf: canvas.Canvas, text: str, width: float, font: str, size: float) -> list[str]:
    """Greedy word wrap against the real string widths of the chosen font.

    Measured rather than counted: "Mitgliedsbescheinigung" and
    "iiiiiiiiiiiiiiiiiiiiii" have the same length and nothing else.
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

        # German compounds get long — "eintausendzweihundertvierunddreißig"
        # does not fit a column, and a word that cannot be broken would
        # otherwise be drawn straight over whatever sits to its right.
        while pdf.stringWidth(current, font, size) > width and len(current) > 1:
            cut = len(current) - 1
            while cut > 1 and pdf.stringWidth(current[:cut], font, size) > width:
                cut -= 1
            lines.append(current[:cut])
            current = current[cut:]

    lines.append(current)
    return lines


def hairline(pdf: canvas.Canvas, x1: float, x2: float, y: float) -> None:
    pdf.setStrokeGray(HAIRLINE)
    pdf.setLineWidth(0.4)
    pdf.line(x1, y, x2, y)


def masthead(
    pdf: canvas.Canvas,
    width: float,
    y: float,
    *,
    club_name: str,
    address_lines: tuple[str, ...] = (),
) -> float:
    """Who is speaking, set small and quiet above the document's own title.

    The club's name belongs at the top of anything it hands out, but it is not
    the headline — what the reader is holding is. So it goes up here in small
    tracked capitals and gets out of the way.
    """
    pdf.setFont("Helvetica-Bold", LABEL)
    pdf.setFillGray(STRONG)
    tracked(pdf, MARGIN, y, club_name.upper(), LABEL_TRACKING)

    if address_lines:
        pdf.setFont("Helvetica", FOOTNOTE)
        pdf.setFillGray(MUTED)
        pdf.drawRightString(width - MARGIN, y, " · ".join(address_lines))

    y -= 4 * mm
    hairline(pdf, MARGIN, width - MARGIN, y)
    pdf.setFillGray(INK)
    return y - 14 * mm


def title(
    pdf: canvas.Canvas,
    width: float,
    y: float,
    *,
    text: str,
    subtitle: str | None = None,
) -> float:
    """The document's own headline, and the sentence that qualifies it."""
    pdf.setFillGray(INK)
    pdf.setFont("Helvetica-Bold", TITLE)
    for line in wrap(pdf, text, width - 2 * MARGIN, "Helvetica-Bold", TITLE):
        pdf.drawString(MARGIN, y, line)
        y -= 8 * mm

    if subtitle:
        y += 2 * mm
        pdf.setFont("Helvetica", SUBTITLE)
        pdf.setFillGray(MUTED)
        for line in wrap(pdf, subtitle, width - 2 * MARGIN, "Helvetica", SUBTITLE):
            pdf.drawString(MARGIN, y, line)
            y -= 4.4 * mm
        pdf.setFillGray(INK)

    return y - 6 * mm


def section(pdf: canvas.Canvas, width: float, y: float, text: str) -> float:
    """A tracked capital label over a hairline — the only kind of heading here."""
    pdf.setFont("Helvetica-Bold", LABEL)
    pdf.setFillGray(MUTED)
    tracked(pdf, MARGIN, y, text.upper(), LABEL_TRACKING)
    pdf.setFillGray(INK)
    y -= 2.5 * mm
    hairline(pdf, MARGIN, width - MARGIN, y)
    return y - 7 * mm


def facts(
    pdf: canvas.Canvas,
    width: float,
    y: float,
    items: tuple[tuple[str, str], ...],
    *,
    columns: int = 2,
    emphasise: frozenset[str] = frozenset(),
) -> float:
    """Label above value, in columns.

    Stacked rather than label-left/value-right across the whole page: at A4
    width that layout leaves a canyon between the two, and the eye has to
    travel it for every row.

    A value too long for its column wraps onto a second line and no further —
    a fact that needs three lines is a paragraph, and belongs in one.
    """
    if not items:
        return y

    usable = width - 2 * MARGIN
    gutter = 8 * mm
    column_width = (usable - gutter * (columns - 1)) / columns
    line_height = 4.2 * mm
    row_height = 13 * mm

    row_top = y
    for start in range(0, len(items), columns):
        # A row is as tall as its tallest cell — otherwise a value that wraps
        # runs into the label of the row below it.
        tallest = 1
        for column, (label, value) in enumerate(items[start : start + columns]):
            x = MARGIN + column * (column_width + gutter)

            pdf.setFont("Helvetica", LABEL)
            pdf.setFillGray(MUTED)
            tracked(pdf, x, row_top, label.upper(), LABEL_TRACKING)

            strong = label in emphasise
            font = "Helvetica-Bold" if strong else "Helvetica"
            size = HEADING + 1 if strong else HEADING
            pdf.setFont(font, size)
            pdf.setFillGray(INK)
            lines = wrap(pdf, value, column_width, font, size)[:2]
            tallest = max(tallest, len(lines))
            for offset, line in enumerate(lines):
                pdf.drawString(x, row_top - 5 * mm - offset * line_height, line)

        row_top -= row_height + (tallest - 1) * line_height

    return row_top


def paragraph(
    pdf: canvas.Canvas,
    width: float,
    y: float,
    text: str,
    *,
    size: float = BODY,
    gray: float = INK,
    gap: float = 3 * mm,
    leading: float = BODY_LEADING,
) -> float:
    """One block of flowing text. Blank lines are the caller's business."""
    pdf.setFont("Helvetica", size)
    pdf.setFillGray(gray)
    for line in wrap(pdf, text, width - 2 * MARGIN, "Helvetica", size):
        pdf.drawString(MARGIN, y, line)
        y -= leading
    pdf.setFillGray(INK)
    return y - gap


def signature_line(pdf: canvas.Canvas, y: float, caption: str) -> float:
    pdf.setStrokeGray(0.55)
    pdf.setLineWidth(0.5)
    pdf.line(MARGIN, y, MARGIN + 70 * mm, y)
    y -= 4 * mm
    pdf.setFont("Helvetica", FOOTNOTE)
    pdf.setFillGray(MUTED)
    pdf.drawString(MARGIN, y, caption)
    pdf.setFillGray(INK)
    return y - 6 * mm


def revoked_notice(pdf: canvas.Canvas, width: float, y: float, text: str) -> float:
    """Says the document is void, on its face.

    The check page is the second line of defence, not the first — somebody
    holding a printout should not have to scan a code to find out.
    """
    height = 9 * mm
    pdf.setFillColorRGB(*REVOKED_COLOR)
    pdf.rect(MARGIN, y - height + 2.5 * mm, 1.2 * mm, height, stroke=0, fill=1)
    pdf.setFont("Helvetica-Bold", SMALL + 0.5)
    pdf.drawString(MARGIN + 4 * mm, y, text)
    pdf.setFillGray(INK)
    return y - height - 2 * mm


def footer(
    pdf: canvas.Canvas,
    width: float,
    *,
    lines: tuple[str, ...] = (),
    check_lines: tuple[str, ...] = (),
    qr_size: float = 0,
) -> None:
    """Register data and the check block, pinned to the bottom.

    Pinned rather than following the text: a reader looking for the check code
    should find it in the same place on every document a club issues.
    """
    baseline = MARGIN
    if lines:
        pdf.setFont("Helvetica", FOOTNOTE)
        pdf.setFillGray(MUTED)
        pdf.drawRightString(width - MARGIN, baseline, " · ".join(lines))

    if check_lines:
        x = MARGIN + (qr_size + 5 * mm if qr_size else 0)
        y = baseline + (qr_size - 3 * mm if qr_size else 8 * mm)
        pdf.setFont("Helvetica", FOOTNOTE)
        pdf.setFillGray(MUTED)
        for line in check_lines:
            pdf.drawString(x, y, line)
            y -= 3.6 * mm

    pdf.setFillGray(INK)


def footer_rule(pdf: canvas.Canvas, width: float, y: float) -> None:
    hairline(pdf, MARGIN, width - MARGIN, y)
