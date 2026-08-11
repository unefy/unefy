"""Ready-made wordings a club can start from.

**Drafts, not legal advice.** These are the letters German clubs write most
often, phrased conservatively: they confirm facts the club actually holds and
promise nothing beyond them. What a club may certify follows from its own
articles and from who is asking, and neither is knowable here — so every
starter carries a `caveat` naming what to check, and nothing is installed
without somebody reading it first.

Deliberately absent: the **Zuwendungsbestätigung** (donation receipt). It
follows an official template published by the tax administration, and rebuilding
it as free text is exactly the invitation to produce an invalid document that
kept prescribed forms out of this feature in the first place. It belongs in
code, as its own document, or not at all.

Also absent: anything that would state a sum paid over a period. The dues are
in the system, but a statement of payments needs a year to be chosen at issuing
time, and this feature has no per-issue input. Better none than one that
silently reports the wrong period.
"""

from dataclasses import dataclass

from app.schemas.document import SignatureMode


@dataclass(frozen=True)
class StarterTemplate:
    """One ready-made wording, plus what the club has to look at."""

    key: str
    name: str
    title: str
    body: str
    #: What the club should check or adapt before using it. Shown next to the
    #: text in the editor, never printed on the document.
    caveat: str
    include_letterhead: bool = True
    include_footer: bool = True
    verifiable: bool = True
    #: `none`, `machine` or `line` — see `DocumentTemplate.signature_mode`.
    #: Chosen per starter rather than defaulted, because whether a document is
    #: signed by hand is the whole difference between a certificate a club
    #: mails out and one it hands over at the counter.
    signature_mode: SignatureMode = "line"


MEMBERSHIP = StarterTemplate(
    key="membership",
    name="Mitgliedsbescheinigung",
    signature_mode="machine",
    title="Mitgliedsbescheinigung",
    body="""Hiermit bestätigen wir, dass

{{mitglied.name}}, geboren am {{mitglied.geburtstag}},
wohnhaft {{mitglied.anschrift}},

seit dem {{mitglied.eintritt}} Mitglied im {{verein.name}} ist.
Die Mitgliedsnummer lautet {{mitglied.nummer}}.

Die Mitgliedschaft besteht zum Zeitpunkt der Ausstellung dieser Bescheinigung.

Diese Bescheinigung wird auf Wunsch des Mitglieds ausgestellt.

{{datum}}""",
    caveat=(
        "Prüfen Sie, ob der Empfänger Geburtsdatum und Anschrift wirklich "
        "benötigt — je weniger die Bescheinigung nennt, desto weniger gibt sie "
        "preis. Beides lässt sich hier streichen."
    ),
)

MEMBERSHIP_WITH_FEE = StarterTemplate(
    key="membership_fee",
    name="Mitgliedsbescheinigung mit Beitrag",
    signature_mode="machine",
    title="Mitgliedsbescheinigung",
    body="""Hiermit bestätigen wir, dass

{{mitglied.name}}, geboren am {{mitglied.geburtstag}},

seit dem {{mitglied.eintritt}} Mitglied im {{verein.name}} ist
(Mitgliedsnummer {{mitglied.nummer}}).

Der Mitgliedsbeitrag beträgt derzeit {{mitglied.beitrag}}.
Beitragsart: {{mitglied.beitragsart}}.

Diese Bescheinigung dient der Vorlage bei Arbeitgeber, Krankenkasse oder
einer vergleichbaren Stelle. Über die Anerkennung entscheidet die
empfangende Stelle.

{{datum}}""",
    caveat=(
        "Der genannte Beitrag ist der am Ausstellungstag gültige, nicht die "
        "im Jahr tatsächlich gezahlte Summe. Als Spendenquittung ist diese "
        "Bescheinigung ausdrücklich nicht geeignet — dafür gilt das amtliche "
        "Muster der Finanzverwaltung."
    ),
)

RESIGNATION = StarterTemplate(
    key="resignation",
    name="Austrittsbestätigung",
    signature_mode="machine",
    title="Bestätigung des Austritts",
    body="""Sehr geehrte(s) Mitglied {{mitglied.name}},

hiermit bestätigen wir den Eingang Ihrer Kündigung der Mitgliedschaft im
{{verein.name}}.

Ihre Mitgliedschaft (Mitgliedsnummer {{mitglied.nummer}}), begonnen am
{{mitglied.eintritt}}, endet mit Ablauf des {{mitglied.austritt}}.

Beiträge für Zeiträume nach diesem Datum werden nicht mehr erhoben. Bis
dahin entstandene Forderungen bleiben davon unberührt.

Wir bedanken uns für Ihre Mitgliedschaft.

{{datum}}""",
    caveat=(
        "Das Austrittsdatum kommt aus dem Mitgliedsdatensatz und muss dort "
        "vorher eingetragen sein — sonst steht hier ein Strich. Ob der "
        "Austritt zu diesem Termin überhaupt wirksam ist, richtet sich nach "
        "der Kündigungsfrist Ihrer Satzung."
    ),
    # Nothing here that anybody would forge, and a check code on a farewell
    # letter is ceremony.
    verifiable=False,
)

VOLUNTEER = StarterTemplate(
    key="volunteer",
    name="Bescheinigung über ehrenamtliche Tätigkeit",
    signature_mode="line",
    title="Bescheinigung über ehrenamtliche Tätigkeit",
    body="""Hiermit bestätigen wir, dass

{{mitglied.name}}, geboren am {{mitglied.geburtstag}},

Mitglied im {{verein.name}} ist und dort ehrenamtlich mitarbeitet.

Übernommene Ämter: {{mitglied.aemter}}
Mitglied seit: {{mitglied.eintritt}}

Die Tätigkeit erfolgt im Rahmen der Vereinsarbeit.

{{datum}}""",
    caveat=(
        "Es werden die am Ausstellungstag laufenden Ämter genannt; frühere "
        "erscheinen nicht. Ergänzen Sie Umfang oder Zeitraum, wenn der "
        "Empfänger das verlangt. Zu einer gezahlten Ehrenamts- oder "
        "Übungsleiterpauschale sagt diese Bescheinigung bewusst nichts."
    ),
)

ANNIVERSARY = StarterTemplate(
    key="anniversary",
    name="Urkunde für langjährige Mitgliedschaft",
    signature_mode="line",
    title="Urkunde",
    body="""Der {{verein.name}} ehrt

{{mitglied.name}}

für {{mitglied.mitgliedsjahre}} Jahre Mitgliedschaft.

Wir danken für die langjährige Treue und die Verbundenheit mit unserem
Verein.

{{datum}}""",
    caveat=(
        "Die Jahre werden aus dem Eintrittsdatum gerechnet und auf volle "
        "Jahre abgerundet. Für eine Ehrung zum Jubiläumsjahr prüfen Sie das "
        "Datum, bevor Sie ausstellen."
    ),
    # An honour, not evidence: nobody checks a certificate of thanks, and a
    # QR on it would look like distrust.
    verifiable=False,
    include_footer=False,
)

STARTERS: tuple[StarterTemplate, ...] = (
    MEMBERSHIP,
    MEMBERSHIP_WITH_FEE,
    RESIGNATION,
    VOLUNTEER,
    ANNIVERSARY,
)


def starter_by_key(key: str) -> StarterTemplate | None:
    return next((s for s in STARTERS if s.key == key), None)
