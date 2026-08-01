"""Sport modules — the one place where database configuration points at code.

A module bundles sport-specific tables, endpoints and screens (e.g. the
shooting module's §14 WaffG attendance proof). A module therefore cannot be
created through the admin UI; only the *assignment* of an existing module to a
sport is configuration.

`sports.modules` is validated against this registry on write, so a sport can
never reference a module that has no implementation behind it.
"""

# Module key -> human-readable label for the admin UI.
AVAILABLE_MODULES: dict[str, str] = {
    "shooting": "Schießsport (Schießnachweis, WBK, Verbandsmeldung)",
}


def unknown_modules(modules: list[str]) -> list[str]:
    """Return the entries that have no implementation registered."""
    return [module for module in modules if module not in AVAILABLE_MODULES]
