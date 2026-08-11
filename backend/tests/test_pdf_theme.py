"""What the shared document look has to keep doing.

The three renderers are covered through their endpoints elsewhere. What is
asserted here is the layout engine underneath them: that pages break, that
club-authored text cannot break the document, and that the letterspacing on
the small capitals stays on the small capitals.
"""

import re
from datetime import date

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import Table

from app.services import pdf_theme as theme
from app.services.certificate_pdf import (
    CertificateDay,
    CertificateDocument,
    _annex,
    build_certificate_pdf,
)
from app.services.document_pdf import DocumentLetter, build_document_pdf

CLUB = "Schützenverein Eichstetten am Kaiserstuhl e. V."


def _pages(pdf_bytes: bytes) -> int:
    """How many pages the file has, counted on the objects themselves.

    `/Type /Pages` is the tree node and must not be counted with them.
    """
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf_bytes))


def _line_width(flowable: object) -> float:
    """How wide the longest laid-out line of a paragraph actually is."""
    flowable.wrap(400, 400)  # type: ignore[attr-defined]
    return float(max(flowable.getActualLineWidths0()))  # type: ignore[attr-defined]


def _letter(body: str, **kwargs: object) -> DocumentLetter:
    return DocumentLetter(
        club_name=CLUB,
        title="Mitgliedsbescheinigung",
        body=body,
        issued_on=date(2026, 8, 11),
        **kwargs,  # type: ignore[arg-type]
    )


def test_a_long_document_runs_onto_further_pages() -> None:
    """The club writes the text, so its length is not ours to bound.

    The renderer hands the text to the layout engine and never counts
    millimetres — this is the assertion that keeps it that way.
    """
    short = build_document_pdf(_letter("Kurz und gut."))
    long_body = "\n\n".join("Ein Absatz über den Verein. " * 12 for _ in range(20))

    assert _pages(short) == 1
    assert _pages(build_document_pdf(_letter(long_body))) > 1


def test_the_furniture_is_drawn_on_every_page(monkeypatch: pytest.MonkeyPatch) -> None:
    """A second sheet that has come loose from the first still has to say
    which club wrote it and how to check it.

    Counted through the page callback rather than read off the page: the font
    is embedded as a subset, so the drawn strings are glyph codes and a
    search for the club's name in the file finds nothing.
    """
    drawn = []
    real = theme._draw_furniture
    monkeypatch.setattr(
        theme,
        "_draw_furniture",
        lambda pdf, width, height, page: (drawn.append(page), real(pdf, width, height, page))[1],
    )

    body = "\n\n".join("Ein Absatz über den Verein. " * 12 for _ in range(20))
    document = build_document_pdf(
        _letter(
            body,
            letterhead=("Am Schießstand 3", "79356 Eichstetten"),
            verification_code="M4T7XQ2BKR9",
            verification_url="https://app.unefy.de/verify/M4T7XQ2BKR9",
        )
    )

    pages = _pages(document)
    assert pages > 1
    assert len(drawn) == pages
    assert all(page.address_lines and page.has_check for page in drawn)


def test_club_text_is_text_and_not_markup() -> None:
    """The layout engine parses paragraphs as XML.

    Unescaped, a club that writes "Beitragsgruppe <Jugend>" gets an exception
    instead of a certificate, and one that writes `<b>` gets bold text it
    never asked for.
    """
    assert theme.text("Beitrag < 50 & Zuschlag > 0") == "Beitrag &lt; 50 &amp; Zuschlag &gt; 0"
    # A typed newline is a line break; an address block is written that way.
    assert theme.rich("Maria\nFreiburg") == "Maria<br/>Freiburg"

    # Unescaped, reportlab reads "<Jugend>" as a tag and silently swallows it —
    # no exception, just a sentence with a hole in it. Measured against the
    # same sentence in round brackets, which nothing could mistake for markup.
    brackets = _line_width(theme.paragraph("Beitragsgruppe <Jugend> wird fortgeführt"))
    parens = _line_width(theme.paragraph("Beitragsgruppe (Jugend) wird fortgeführt"))
    assert abs(brackets - parens) < 5

    document = build_document_pdf(
        _letter("Beitragsgruppe <Jugend> wird fortgeführt. Kein <b>Markup</b>, sondern Text.")
    )

    assert document.startswith(b"%PDF")
    assert _pages(document) == 1


def test_the_annex_carries_its_header_onto_every_page() -> None:
    """A long list of range days must not turn into unlabelled numbers."""
    days = tuple(
        CertificateDay(
            day=date(2026, 1 + index // 20, 1 + index % 20),
            discipline="25 m Großkaliber Präzision",
            weapon_category="kurzwaffe",
            rounds_fired=30,
            origin="club",
        )
        for index in range(60)
    )
    certificate = _certificate(days=days)

    # Certificate plus an annex over more than one page.
    assert _pages(build_certificate_pdf(certificate)) > 2
    # And the header row travels with it. Asserted on the table rather than on
    # the page, because the embedded font is subsetted and the drawn strings
    # are glyph codes rather than the words "Datum" and "Disziplin".
    tables = [flowable for flowable in _annex(certificate) if isinstance(flowable, Table)]
    assert [table.repeatRows for table in tables] == [1]


def _certificate(**kwargs: object) -> CertificateDocument:
    return CertificateDocument(
        club_name=CLUB,
        member_name="Maria Musterfrau",
        member_number="0421",
        rule_label="§ 14 Abs. 3 WaffG",
        period_start=date(2025, 8, 1),
        period_end=date(2026, 7, 31),
        session_count=21,
        months_covered=9,
        self_certified_days=0,
        external_days=0,
        passed=True,
        issued_on=date(2026, 8, 11),
        verification_code="7KQ4M2XVBN3",
        verification_url="https://app.unefy.de/verify/7KQ4M2XVBN3",
        **kwargs,  # type: ignore[arg-type]
    )


def test_the_font_travels_inside_the_document() -> None:
    """A club prints this and hands it over. Whether the recipient happens to
    have the typeface installed is not something the layout may depend on."""
    document = build_certificate_pdf(_certificate())

    assert b"FiraSans" in document
    assert b"FontFile2" in document


def test_letterspacing_does_not_leak_out_of_the_label() -> None:
    """Character spacing is part of the graphics state and outlives the text
    object that set it.

    Left standing it widened every later string on the page while
    `stringWidth` — what right-aligned text anchors on — kept measuring them
    without it, and the footer walked off the right edge. Asserted on the
    content stream because that is the only place the leak exists.
    """
    pdf = canvas.Canvas("/dev/null", pagesize=A4)
    theme.tracked(pdf, 0, 0, "VEREIN", theme.LABEL_TRACKING)
    code = " ".join(pdf.getCurrentPageContent().split())

    spacing = re.search(r"(-?[\d.]+) Tc", code)
    assert spacing is not None, code
    assert float(spacing.group(1)) == theme.LABEL_TRACKING
    # It is set inside a saved state, and the state is given back afterwards.
    assert re.search(r"q .* Tc .* Q", code), code
