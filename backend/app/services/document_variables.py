"""The placeholders a club may put in a document template.

One fixed, documented set — not an expression language. A template is text
with names in it, and rendering is a dictionary lookup: nothing is evaluated,
so there is nothing to inject, and the printed result is predictable from the
template alone.

This module is the single source of truth for that set. It feeds three things
that must not drift apart: the completion list the editor offers, the check
that refuses an unknown placeholder on save, and the substitution at issuing
time. A fourth place would be a fourth chance to disagree.

The names are German because the people writing the templates are.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.models.member import Member
from app.models.tenant import Tenant

#: `{{ name }}` with any amount of inner space. Deliberately narrow: only
#: letters, digits, dots and underscores are a name, so a stray brace in prose
#: cannot become a half-recognised placeholder.
PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")

#: What an unset value prints as. Not an empty string: a gap in a certificate
#: should be visible to whoever signs it, and the preview is where it gets
#: caught. Not an error either — refusing to issue because one field is blank
#: would be the system overruling the person holding the pen.
EMPTY = "—"


@dataclass(frozen=True)
class Variable:
    key: str
    #: Short English note. The German label the editor shows lives in the web
    #: app's message files, keyed by `key` — UI text belongs there, not here.
    description: str


VARIABLES: tuple[Variable, ...] = (
    Variable("mitglied.name", "Full name of the member"),
    Variable("mitglied.vorname", "First name"),
    Variable("mitglied.nachname", "Last name"),
    Variable("mitglied.nummer", "Member number"),
    Variable("mitglied.geburtstag", "Date of birth"),
    Variable("mitglied.eintritt", "Date of joining"),
    Variable("mitglied.austritt", "Date of leaving, if any"),
    Variable("mitglied.status", "Membership status"),
    Variable("mitglied.anschrift", "Address on one line"),
    Variable("verein.name", "Club name"),
    Variable("verein.anschrift", "Club address on one line"),
    Variable("verein.registernummer", "Register number"),
    Variable("verein.registergericht", "Registering court"),
    Variable("datum", "Today's date in the club's time zone"),
    Variable("jahr", "Current year in the club's time zone"),
)

VARIABLE_KEYS = frozenset(v.key for v in VARIABLES)

STATUS_LABELS = {
    "active": "aktiv",
    "inactive": "inaktiv",
    "passive": "passiv",
    "honorary": "Ehrenmitglied",
    "left": "ausgetreten",
}


def unknown_placeholders(body: str) -> list[str]:
    """Names in the text that are not in the set, in order of appearance.

    Returned rather than raised so the caller can name all of them at once —
    telling somebody about one typo at a time is a poor way to edit a letter.
    """
    seen: list[str] = []
    for match in PLACEHOLDER.finditer(body):
        name = match.group(1)
        if name not in VARIABLE_KEYS and name not in seen:
            seen.append(name)
    return seen


def _german_date(value: date | None) -> str:
    return value.strftime("%d.%m.%Y") if value else EMPTY


def _one_line(*parts: str | None) -> str:
    joined = ", ".join(p.strip() for p in parts if p and p.strip())
    return joined or EMPTY


def build_values(member: Member, tenant: Tenant) -> dict[str, str]:
    """Resolve every variable for this member and club.

    Every key is present, so rendering never has to decide what a missing name
    means — `EMPTY` already is that decision, taken once.

    "Today" is the club's day, not the server's: a certificate dated the 31st
    because the server is in UTC and the office is in Berlin is wrong on paper
    in a way nobody would think to check.
    """
    zone = ZoneInfo(tenant.timezone)
    today = datetime.now(zone).date()

    return {
        "mitglied.name": f"{member.first_name} {member.last_name}".strip() or EMPTY,
        "mitglied.vorname": member.first_name or EMPTY,
        "mitglied.nachname": member.last_name or EMPTY,
        "mitglied.nummer": member.member_number or EMPTY,
        "mitglied.geburtstag": _german_date(member.birthday),
        "mitglied.eintritt": _german_date(member.joined_at),
        "mitglied.austritt": _german_date(member.left_at),
        "mitglied.status": STATUS_LABELS.get(member.status, member.status),
        "mitglied.anschrift": _one_line(
            member.street,
            " ".join(p for p in (member.zip_code, member.city) if p),
            member.country,
        ),
        "verein.name": tenant.name or EMPTY,
        "verein.anschrift": _one_line(
            tenant.street,
            " ".join(p for p in (tenant.zip_code, tenant.city) if p),
            tenant.country,
        ),
        "verein.registernummer": tenant.registration_number or EMPTY,
        "verein.registergericht": tenant.registration_court or EMPTY,
        "datum": _german_date(today),
        "jahr": str(today.year),
    }


def render(body: str, values: dict[str, str]) -> str:
    """Substitute the placeholders. Nothing else happens to the text.

    An unknown name is left standing rather than blanked. It cannot normally
    get this far — saving a template rejects it — but if it ever does, a
    visible `{{typo}}` on the preview is better than a silent hole in a
    document somebody is about to sign.
    """
    return PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), body)


def sample_values(
    club_name: str = "Musterverein e. V.", timezone: str = "Europe/Berlin"
) -> dict[str, str]:
    """Stand-in values for previewing a template without picking a member.

    Obviously fake on sight: somebody proof-reading the wording should never
    have to wonder whether they are looking at a real person's data.

    The date is the club's, like everywhere else. A preview that shows
    yesterday because the server runs in UTC would send somebody looking for a
    bug in the placeholder.
    """
    today = datetime.now(ZoneInfo(timezone)).date()
    return {
        "mitglied.name": "Erika Mustermann",
        "mitglied.vorname": "Erika",
        "mitglied.nachname": "Mustermann",
        "mitglied.nummer": "0042",
        "mitglied.geburtstag": "01.03.1985",
        "mitglied.eintritt": "01.01.2020",
        "mitglied.austritt": EMPTY,
        "mitglied.status": "aktiv",
        "mitglied.anschrift": "Musterweg 1, 12345 Musterstadt",
        "verein.name": club_name,
        "verein.anschrift": "Vereinsstraße 2, 12345 Musterstadt",
        "verein.registernummer": "VR 1234",
        "verein.registergericht": "Amtsgericht Musterstadt",
        "datum": _german_date(today),
        "jahr": str(today.year),
    }


def content_hash_input(member_id: uuid.UUID, body: str, issued_at: datetime) -> str:
    """The canonical string a document's hash is taken over."""
    return f"{member_id}|{issued_at.isoformat()}|{body}"
