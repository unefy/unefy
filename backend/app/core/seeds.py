"""Locale-aware seed data applied at tenant creation.

These seeds are intentionally duplicated across locales (not i18n-resolved at
read time) because clubs may want to rename individual entries after they
start using them. We seed sensible defaults for the user's locale, and from
there every label is user content.
"""

import json

# Stable keys referenced by UI logic. Do NOT rename after release.
MEMBER_STATUS_KEYS = ("active", "inactive", "resigned", "terminated", "deceased")

_MEMBER_STATUS_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "active": "Active",
        "inactive": "Inactive",
        "resigned": "Resigned",
        "terminated": "Terminated",
        "deceased": "Deceased",
    },
    "de": {
        "active": "Aktiv",
        "inactive": "Inaktiv",
        "resigned": "Ausgetreten",
        "terminated": "Gekündigt",
        "deceased": "Verstorben",
    },
}


def member_statuses_seed(locale: str | None) -> str:
    """Return the JSON seed for `tenants.member_statuses` for the given locale.

    Falls back to English if the locale is unknown or None.
    """
    normalized = (locale or "en").lower()
    lang = normalized.split("-", 1)[0]
    labels = _MEMBER_STATUS_LABELS.get(lang) or _MEMBER_STATUS_LABELS["en"]
    return json.dumps(
        [{"key": key, "label": labels[key]} for key in MEMBER_STATUS_KEYS],
        ensure_ascii=False,
        separators=(",", ":"),
    )
