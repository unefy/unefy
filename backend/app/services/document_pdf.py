"""The printable free-form document: letterhead, the club's text, a QR.

The counterpart to `certificate_pdf`. That one draws a prescribed form and
knows every field it prints. This one knows nothing about the content — the
club wrote it — and only hands the text to the layout engine.

How it looks, and where the pages break, is `pdf_theme`'s business.
"""

from dataclasses import dataclass
from datetime import date

from reportlab.platypus import Flowable, Spacer

from app.services import pdf_theme as theme
from app.services.pdf_theme import mm

REVOKED_TEXT = "WIDERRUFEN — dieses Dokument ist ungültig"

#: Said plainly, because a blank space where a signature belongs reads as an
#: oversight. The second sentence is only true when the document carries a
#: check code, so it is only printed then.
MACHINE_TEXT = "Dieses Dokument wurde maschinell erstellt und ist ohne Unterschrift gültig."
MACHINE_TEXT_VERIFIABLE = (
    "Dieses Dokument wurde maschinell erstellt und ist ohne Unterschrift gültig. "
    "Seine Echtheit lässt sich mit dem Prüfcode am Fuß dieser Seite bestätigen."
)


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

    #: Caption under a ruled line the club signs by hand. Absent when the
    #: template asked for no signature or for the machine-made note.
    signature_line: str | None = None
    #: Says the document is valid without one. Printed instead of the line, not
    #: beside it — a document cannot both want a signature and not need one.
    machine_made: bool = False


def _de(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def build_document_pdf(doc: DocumentLetter) -> bytes:
    """Render one document to PDF bytes, over as many pages as it needs.

    The club writes the text, so the length is not ours to bound. Running onto
    a second page is normal here, unlike the §14 certificate.
    """
    story: list[Flowable] = list(theme.title(doc.title))
    if doc.revoked:
        story.append(theme.revoked_notice(REVOKED_TEXT))

    for block in doc.body.split("\n\n"):
        story.append(theme.paragraph(block, keep_breaks=True))
        story.append(Spacer(0, 3 * mm))

    if doc.signature_line:
        story.append(theme.signature(doc.signature_line))
    elif doc.machine_made:
        story.append(Spacer(0, 8 * mm))
        story.append(
            theme.paragraph(
                MACHINE_TEXT_VERIFIABLE if doc.verification_code else MACHINE_TEXT,
                style=theme.FOOTNOTE_STYLE,
            )
        )

    return theme.build(
        story,
        page=theme.Furniture(
            club_name=doc.club_name,
            address_lines=doc.letterhead,
            footer_lines=(*doc.footer, f"Ausgestellt am {_de(doc.issued_on)}"),
            verification_url=doc.verification_url,
            verification_code=doc.verification_code,
        ),
        pdf_title=doc.title,
    )
