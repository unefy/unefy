import re
import uuid

# German umlauts must expand rather than be stripped: "Schützenverein" should
# become "schuetzenverein", not "schtzenverein".
_TRANSLITERATIONS = str.maketrans(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
        "é": "e",
        "è": "e",
        "ê": "e",
        "á": "a",
        "à": "a",
        "â": "a",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "ú": "u",
        "ç": "c",
        "ñ": "n",
    }
)

MAX_SLUG_LENGTH = 60


def slugify(value: str) -> str:
    """Turn a display name into a URL-safe slug.

    Returns an empty string when nothing usable remains (e.g. a name made
    entirely of punctuation) — callers decide on the fallback.
    """
    text = value.translate(_TRANSLITERATIONS).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:MAX_SLUG_LENGTH].strip("-")


def fallback_slug() -> str:
    return f"club-{uuid.uuid4().hex[:8]}"
