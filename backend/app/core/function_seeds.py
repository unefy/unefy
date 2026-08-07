"""Seed content for the global club-function catalog (`catalog_functions`).

Initial content only — after the first migration the catalog is maintained by
platform admins, not by editing this file. `sport_key` of None means a general
office every club gets; otherwise the office is copied only for clubs that
chose that sport at onboarding.

`suggested_role` is a recommendation the UI surfaces when assigning the
function — auth roles are never coupled automatically.
"""

from typing import TypedDict


class FunctionSeed(TypedDict):
    sport_key: str | None
    key: str
    name: str
    level: str
    suggested_role: str | None
    sort_order: int


CATALOG_FUNCTIONS: list[FunctionSeed] = [
    # --- General offices, all sports ---
    {
        "sport_key": None,
        "key": "chairperson",
        "name": "1. Vorsitzende:r",
        "level": "club",
        "suggested_role": "admin",
        "sort_order": 10,
    },
    {
        "sport_key": None,
        "key": "vice_chairperson",
        "name": "2. Vorsitzende:r",
        "level": "club",
        "suggested_role": "board",
        "sort_order": 20,
    },
    {
        "sport_key": None,
        "key": "treasurer",
        "name": "Kassier",
        "level": "club",
        "suggested_role": "board",
        "sort_order": 30,
    },
    {
        "sport_key": None,
        "key": "secretary",
        "name": "Schriftführer:in",
        "level": "club",
        "suggested_role": "board",
        "sort_order": 40,
    },
    {
        "sport_key": None,
        "key": "assessor",
        "name": "Beisitzer:in",
        "level": "club",
        "suggested_role": None,
        "sort_order": 50,
    },
    {
        "sport_key": None,
        "key": "auditor",
        "name": "Kassenprüfer:in",
        "level": "club",
        "suggested_role": None,
        "sort_order": 60,
    },
    {
        "sport_key": None,
        "key": "youth_leader",
        "name": "Jugendleiter:in",
        "level": "club",
        "suggested_role": "board",
        "sort_order": 70,
    },
    {
        "sport_key": None,
        "key": "division_leader",
        "name": "Abteilungsleiter:in",
        "level": "division",
        "suggested_role": "board",
        "sort_order": 80,
    },
    # --- Shooting sport ---
    {
        "sport_key": "shooting",
        "key": "shooting_master",
        "name": "Schützenmeister",
        "level": "club",
        "suggested_role": "board",
        "sort_order": 110,
    },
    {
        "sport_key": "shooting",
        "key": "sport_leader",
        "name": "Sportleiter",
        "level": "club",
        "suggested_role": "board",
        "sort_order": 120,
    },
    {
        "sport_key": "shooting",
        "key": "armorer",
        "name": "Waffenwart",
        "level": "club",
        "suggested_role": None,
        "sort_order": 130,
    },
    {
        "sport_key": "shooting",
        "key": "range_officer",
        "name": "Schießstandaufsicht",
        "level": "club",
        "suggested_role": None,
        "sort_order": 140,
    },
    {
        "sport_key": "shooting",
        "key": "womens_leader",
        "name": "Damenleiterin",
        "level": "club",
        "suggested_role": None,
        "sort_order": 150,
    },
]
