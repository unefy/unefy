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

How it *looks* is `pdf_theme`'s business, shared with the other documents.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from reportlab.platypus import Flowable, Spacer

from app.services import pdf_theme as theme
from app.services.amount_in_words import euros_in_words
from app.services.pdf_theme import mm

#: The prescribed sentences, in one place so they can be checked and updated
#: against the current official template without reading the renderer.
TEXTS = {
    "title": "Bestätigung über Geldzuwendungen",
    "subtitle": (
        "im Sinne des § 10b des Einkommensteuergesetzes an eine der in § 5 Abs. 1 "
        "Nr. 9 des Körperschaftsteuergesetzes bezeichneten Körperschaften, "
        "Personenvereinigungen oder Vermögensmassen"
    ),
    "waiver_question": "Verzicht auf Erstattung von Aufwendungen",
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


def build_donation_pdf(doc: DonationDocument) -> bytes:
    """Render one donation receipt to PDF bytes."""
    story: list[Flowable] = list(theme.title(TEXTS["title"], TEXTS["subtitle"]))

    if doc.revoked:
        story.append(theme.revoked_notice(TEXTS["revoked"]))

    story.append(theme.section("Zuwendender"))
    story.append(
        theme.facts(
            (
                ("Name", doc.donor_name),
                ("Anschrift", doc.donor_address or "—"),
            )
        )
    )

    story.append(theme.section("Zuwendung"))
    story.append(
        theme.facts(
            (
                ("Betrag in Ziffern", _money(doc.amount)),
                ("Tag der Zuwendung", _de(doc.received_on)),
            ),
            emphasise=frozenset({"Betrag in Ziffern"}),
        )
    )
    # The whole width, because the amount written out is a sentence, not a
    # field: four figures in German run past half an A4 page on their own.
    story.append(theme.facts((("Betrag in Buchstaben", euros_in_words(doc.amount)),), columns=1))
    story.append(
        theme.facts(
            (
                (
                    "Art der Zuwendung",
                    "Mitgliedsbeitrag" if doc.kind == "mitgliedsbeitrag" else "Geldzuwendung",
                ),
                # Printed either way: a blank box is an unanswered question, not a "no".
                (TEXTS["waiver_question"], "Ja" if doc.is_expense_waiver else "Nein"),
            )
        )
    )

    story.append(theme.section("Steuerbegünstigung"))
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
    story.append(theme.paragraph(recognition))
    story.append(Spacer(0, 3 * mm))
    story.append(theme.paragraph(TEXTS["usage"]))

    story.append(theme.signature(TEXTS["signature"]))
    story.append(Spacer(0, 4 * mm))
    # The liability notice is prescribed and long. It sets small and quiet, but
    # it is not a footnote the engine may drop off the page — it flows with the
    # rest and takes a second sheet if the club's purposes need one.
    story.append(theme.paragraph(TEXTS["liability"], style=theme.FOOTNOTE_STYLE))

    return theme.build(
        story,
        page=theme.Furniture(
            club_name=doc.club_name,
            address_lines=(doc.club_address,) if doc.club_address else (),
            footer_lines=(f"Ausgestellt am {_de(doc.issued_on)}",),
            verification_url=doc.verification_url,
            verification_code=doc.verification_code,
        ),
        pdf_title=f"{TEXTS['title']} — {doc.donor_name}",
    )
