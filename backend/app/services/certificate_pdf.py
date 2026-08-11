"""The printable §14 certificate.

A club hands this to an authority, so it has to be a document rather than a
screenshot: the numbers it rests on, and a way to check it against the issuing
server. That last part is the QR — it points at the *web app's* public check
page, not at the API, because whoever scans it is holding a piece of paper and
expects a page, not JSON.

Assembled from flowables rather than drawn: the annex is a list of unknown
length, and where it breaks over pages — carrying its header along — is the
layout engine's job. See `pdf_theme`.
"""

from dataclasses import dataclass
from datetime import date

from reportlab.platypus import Flowable, PageBreak, Paragraph, Spacer, Table, TableStyle

from app.services import pdf_theme as theme
from app.services.pdf_theme import mm

TITLE = "Nachweis über regelmäßiges Schießen"
SUBTITLE = "gemäß § 14 Absatz 2 und 3 Waffengesetz"

REVOKED_TEXT = "WIDERRUFEN — diese Bescheinigung ist ungültig"


@dataclass(frozen=True)
class CertificateDay:
    """One counted range day, for the optional annex.

    No supervisor: the annex goes to an authority, and naming the person who
    kept watch discloses a third party for a purpose the certificate does not
    have. The range book — which does name them — stays the club's own record.
    """

    day: date
    discipline: str | None
    weapon_category: str | None
    rounds_fired: int | None
    #: "club" | "external" — printed, because a self-kept day reads differently.
    origin: str


#: The words the range book uses, so the annex and the CSV agree.
WEAPON_LABELS = {
    "kurzwaffe": "Kurzwaffe",
    "langwaffe": "Langwaffe",
    "luftdruck": "Luftdruck",
}


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
    #: "BDS (Nr. 12345)" per membership. The federation identifies its members
    #: by that number, not by the club's — without it somebody has to match by
    #: hand, and that friction is what sends a document back to paper.
    federations: tuple[str, ...] = ()
    #: Empty unless the annex was asked for.
    days: tuple[CertificateDay, ...] = ()
    #: How many counted records the annex could no longer resolve, because the
    #: retention job removed them. Printed rather than hidden.
    missing_days: int = 0


def _de(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def build_certificate_pdf(doc: CertificateDocument) -> bytes:
    """Render one certificate to PDF bytes."""
    story: list[Flowable] = list(theme.title(TITLE, SUBTITLE))

    if doc.revoked:
        story.append(theme.revoked_notice(REVOKED_TEXT))

    member = doc.member_name
    if doc.member_number:
        member = f"{member} (Mitglied {doc.member_number})"

    rows: list[tuple[str, str]] = [
        ("Mitglied", member),
        ("Zeitraum", f"{_de(doc.period_start)} bis {_de(doc.period_end)}"),
        ("Schießtage", str(doc.session_count)),
        ("Monate mit Terminen", str(doc.months_covered)),
        ("Zugrunde liegende Regel", doc.rule_label),
    ]
    # The real recipient of this document is usually the federation, which
    # issues the Bedürfnisbescheinigung the authority then relies on.
    if doc.federations:
        rows.append(("Verbandsmitgliedschaft", ", ".join(doc.federations)))
    # Named rather than folded into the total: a day that rests on the member's
    # own word is not the same evidence as one a supervisor attested, and a
    # certificate that hides the difference is worth less, not more.
    if doc.self_certified_days or doc.external_days:
        rows.append(
            (
                "Davon selbst geführt",
                f"{doc.self_certified_days} (fremde Stände: {doc.external_days})",
            )
        )

    story.append(theme.section("Nachweis"))
    story.append(theme.facts(tuple(rows), emphasise=frozenset({"Schießtage"})))

    if doc.revoked:
        story.append(theme.verdict("Diese Bescheinigung wurde widerrufen.", theme.REVOKED_COLOR))
    elif doc.passed:
        story.append(
            theme.verdict("Die Voraussetzungen der Regel sind erfüllt.", theme.PASSED_COLOR)
        )
    else:
        story.append(
            theme.verdict("Die Voraussetzungen der Regel sind nicht erfüllt.", theme.REVOKED_COLOR)
        )

    if doc.days:
        story.append(PageBreak())
        story.extend(_annex(doc))

    return theme.build(
        story,
        page=theme.Furniture(
            club_name=doc.club_name,
            footer_lines=(f"Ausgestellt am {_de(doc.issued_on)}",),
            verification_url=doc.verification_url,
            verification_code=doc.verification_code,
        ),
        pdf_title=f"{TITLE} — {doc.member_name}",
    )


def _annex(doc: CertificateDocument) -> list[Flowable]:
    """The counted days, one per row.

    A real table with `repeatRows`, so a list that runs over several pages
    carries its column headings onto each of them instead of turning into
    unlabelled numbers on page three.
    """
    header = ("Datum", "Disziplin", "Waffenart", "Schuss", "Herkunft")
    head_style = theme.TABLE_HEAD_STYLE
    cell_style = theme.TABLE_CELL_STYLE

    data: list[list[Flowable]] = [[Paragraph(theme.text(c), head_style) for c in header]]
    for entry in doc.days:
        data.append(
            [
                Paragraph(theme.text(_de(entry.day)), cell_style),
                Paragraph(theme.text(entry.discipline or "—"), cell_style),
                Paragraph(
                    theme.text(
                        WEAPON_LABELS.get(entry.weapon_category or "", entry.weapon_category or "—")
                    ),
                    cell_style,
                ),
                Paragraph(
                    theme.text(str(entry.rounds_fired) if entry.rounds_fired is not None else "—"),
                    cell_style,
                ),
                Paragraph(
                    theme.text("selbst geführt" if entry.origin == "external" else "Verein"),
                    cell_style,
                ),
            ]
        )

    table = Table(
        data,
        colWidths=[26 * mm, 58 * mm, 26 * mm, 18 * mm, 34 * mm],
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 1.6 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6 * mm),
                ("LINEBELOW", (0, 0), (-1, 0), 0.4, (theme.HAIRLINE,) * 3),
            ]
        )
    )

    notes: list[Flowable] = [
        *theme.title(
            "Anlage: Schießtage im Zeitraum",
            f"{doc.member_name} · {_de(doc.period_start)} bis {_de(doc.period_end)}",
        ),
        table,
        Spacer(0, 5 * mm),
    ]
    if doc.missing_days:
        notes.append(
            theme.paragraph(
                f"{doc.missing_days} gezählte Termine sind wegen der Aufbewahrungsfrist "
                "nicht mehr im Bestand und daher hier nicht aufgeführt.",
                style=theme.FOOTNOTE_STYLE,
            )
        )
    notes.append(
        theme.paragraph(
            "Die Standaufsicht ist im Standbuch des Vereins verzeichnet und wird auf "
            "Verlangen vorgelegt.",
            style=theme.FOOTNOTE_STYLE,
        )
    )
    return notes
