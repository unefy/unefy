"""Ring geometry of the standard shooting targets.

These numbers decide every score in the system, so each row carries the rule it
was taken from. Two conventions run through the whole file:

- `ring_diameters_mm` holds exactly 10 OUTER diameters, index 0 = ring 10
  (innermost), index 9 = ring 1. Ring 1's diameter is the whole scoring area.
- `black_diameter_mm` is a length, not a ring number. On the ISSF 50 m rifle
  target the black is 112.4 mm — between ring 4 (106.4) and ring 3 (122.4) — so
  "black from ring N" cannot express it. It also doubles as the scale anchor for
  photo recognition, which needs the exact physical value.

`caliber_diameter_mm` is only the target's DEFAULT caliber. Scoring is by the
edge of the hole, so the caliber shifts every ring boundary by half its value —
and the same target is shot with different calibers: the 25 m precision target
serves both smallbore (5.6 mm) and the large-bore disciplines (9 mm, .45).
Callers therefore override it per series via `caliber_mm`, and the value that was
actually used is stored on the entry. See `CALIBERS` below.

Sources:
- ISSF Rifle Rules / Pistol Rules, target dimension tables
  https://www.issf-sports.org/theissf/rules.ashx
- DSB Sportordnung (SpO) https://www.dsb.de/sportordnung

Adding a target: verify the diameters against the federation rule, cite it in
`source`, and add a case to `tests/services/test_scoring.py` that pins at least
the 10/9 and 1/miss boundaries. A row whose numbers could not be verified is
seeded with `is_active=False` so it stays out of the client's picker until
somebody checks it — a wrong ring table is worse than a missing one.
"""

from typing import Any

TARGET_TYPES: list[dict[str, Any]] = [
    # =========================================================================
    # Luftdruck 10 m
    # =========================================================================
    {
        "slug": "air_rifle_10m",
        "name": "Luftgewehr 10m",
        # Ring 10 is a 0.5 mm dot; every further ring adds 2.5 mm of radius.
        "ring_diameters_mm": [0.5, 5.5, 10.5, 15.5, 20.5, 25.5, 30.5, 35.5, 40.5, 45.5],
        "inner_ten_diameter_mm": 0.5,
        "black_diameter_mm": 30.5,
        "caliber_diameter_mm": 4.5,
        "caliber_name": "4,5 mm Diabolo",
        "distance_m": 10,
        "source": "ISSF Rifle Rules — 10 m air rifle target",
        "is_active": True,
    },
    {
        "slug": "air_pistol_10m",
        "name": "Luftpistole 10m",
        # Ring width 8 mm in radius.
        "ring_diameters_mm": [11.5, 27.5, 43.5, 59.5, 75.5, 91.5, 107.5, 123.5, 139.5, 155.5],
        "inner_ten_diameter_mm": 5.0,
        "black_diameter_mm": 59.5,
        "caliber_diameter_mm": 4.5,
        "caliber_name": "4,5 mm Diabolo",
        "distance_m": 10,
        "source": "ISSF Pistol Rules — 10 m air pistol target",
        "is_active": True,
    },
    # =========================================================================
    # Kleinkaliber
    # =========================================================================
    {
        "slug": "smallbore_rifle_50m",
        "name": "KK-Gewehr 50m",
        # Ring width 8 mm in radius. Black (112.4) deliberately does not line up
        # with a ring boundary — that is how the target is specified.
        "ring_diameters_mm": [10.4, 26.4, 42.4, 58.4, 74.4, 90.4, 106.4, 122.4, 138.4, 154.4],
        "inner_ten_diameter_mm": 5.0,
        "black_diameter_mm": 112.4,
        "caliber_diameter_mm": 5.6,
        "caliber_name": ".22 lfB (5,6 mm)",
        "distance_m": 50,
        "source": "ISSF Rifle Rules — 50 m rifle target",
        "is_active": True,
    },
    # =========================================================================
    # Scheibe Nr. 5 — Präzision
    #
    # One physical sheet, three slugs. The printed sheet is approved for
    # "Pistole 25/50 m · ISSF · KK 100 m · DSU UIT Präzision", so all three
    # disciplines below share one ring table; they exist as separate rows only
    # because `disciplines.target_type` already points at these slugs and the
    # distance differs. Verified against a real BDS/DSB Nr. 5 sheet.
    #
    # This is the club's main target — 25 m large-bore precision. When something
    # has to work first, it is this one.
    # =========================================================================
    *[
        {
            "slug": slug,
            "name": name,
            # Ring width 25 mm in radius; ring 10 = 50 mm, ring 1 = 500 mm.
            "ring_diameters_mm": [50, 100, 150, 200, 250, 300, 350, 400, 450, 500],
            "inner_ten_diameter_mm": 25.0,
            # Black aiming mark = ring 7. On the printed sheet the 10 ring is
            # filled light, so the black is an annulus — see ml/NOTES-real-targets.md,
            # it matters for the photo pipeline.
            "black_diameter_mm": 200.0,
            # Default only. The 25 m sheet is shot with .22 as well as 9 mm and
            # .45 (DSB 4.60), so the caliber is chosen per series.
            "caliber_diameter_mm": default_caliber,
            "caliber_name": caliber_name,
            "distance_m": distance,
            "source": "BDS/DSB Scheibe Nr. 5 — Pistole 25/50 m, ISSF, KK 100 m, DSU UIT Präzision",
            "is_active": True,
        }
        for slug, name, distance, default_caliber, caliber_name in (
            ("sport_pistol_25m", "25m Präzision (Scheibe Nr. 5)", 25, 9.0, "9 mm Luger"),
            ("free_pistol_50m", "50m Pistole (Scheibe Nr. 5)", 50, 5.6, ".22 lfB (5,6 mm)"),
            (
                "smallbore_rifle_100m",
                "KK-Gewehr 100m (Scheibe Nr. 5)",
                100,
                5.6,
                ".22 lfB (5,6 mm)",
            ),
        )
    ],
]


#: Bullet diameters in mm, for the caliber picker on the recording screen.
#:
#: These are nominal BULLET diameters — what a caliber gauge measures against
#: when a shot sits on a ring line. A hole punched in paper is slightly smaller
#: than the bullet, but the rules score by the bullet, so that is what the
#: scoring service uses.
#:
#: Why this matters here: on the 25 m precision target one ring is 25 mm of
#: radius, and going from .22 (5.6 mm) to .45 (11.5 mm) moves every ring boundary
#: outward by ~3 mm — roughly an eighth of a ring. Getting it wrong is a silent,
#: systematic bias in the shooter's favour or against them.
#:
#: Not a database table: the list is short, changes on the timescale of decades,
#: and clubs need no per-tenant variants. A free-form value can still be sent.
CALIBERS: list[dict[str, Any]] = [
    {"key": "4.5", "name": "4,5 mm Diabolo", "diameter_mm": 4.5},
    {"key": "5.6", "name": ".22 lfB (5,6 mm)", "diameter_mm": 5.6},
    {"key": "7.62", "name": "7,62 mm", "diameter_mm": 7.62},
    {"key": "9", "name": "9 mm Luger", "diameter_mm": 9.0},
    {"key": "357", "name": ".357 Magnum / .38 Special", "diameter_mm": 9.1},
    {"key": "44", "name": ".44 Magnum", "diameter_mm": 10.9},
    {"key": "45", "name": ".45 ACP", "diameter_mm": 11.5},
]
