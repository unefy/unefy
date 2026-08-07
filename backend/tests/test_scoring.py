"""Tests for the ring scoring engine.

These are the reference cases. The Android engine in `core:model` must produce
identical results for the same inputs — that is the only thing keeping the two
implementations from silently drifting apart, so a case added here belongs there
too.

No database: everything works on a `TargetGeometry` built by hand.
"""

import math

import pytest

from app.core.target_type_seeds import TARGET_TYPES
from app.services.scoring import (
    ShotInput,
    TargetGeometry,
    grouping_mm,
    is_inner_ten,
    ring_for,
    score_series,
)


def _geometry(slug: str) -> TargetGeometry:
    entry = next(e for e in TARGET_TYPES if e["slug"] == slug)
    return TargetGeometry(
        slug=slug,
        ring_diameters_mm=tuple(float(d) for d in entry["ring_diameters_mm"]),
        inner_ten_diameter_mm=float(entry["inner_ten_diameter_mm"]),
        black_diameter_mm=float(entry["black_diameter_mm"]),
        default_caliber_mm=float(entry["caliber_diameter_mm"]),
    )


#: The club's main target: 25 m precision, Scheibe Nr. 5.
PRECISION_25M = "sport_pistol_25m"
AIR_RIFLE = "air_rifle_10m"


def _at_mm(distance_mm: float, geometry: TargetGeometry) -> float:
    """Normalised radius for a distance given in millimetres."""
    return distance_mm / geometry.scoring_radius_mm


# --- Basic ring boundaries ---


def test_dead_centre_is_a_ten() -> None:
    geo = _geometry(PRECISION_25M)
    assert ring_for(0.0, geo) == 10


def test_outside_ring_one_is_a_miss() -> None:
    geo = _geometry(PRECISION_25M)
    # Well beyond ring 1 (250 mm radius), further than half a caliber can save.
    assert ring_for(_at_mm(260, geo), geo, caliber_mm=9.0) == 0


def test_every_ring_is_reachable() -> None:
    """Walk outward through the middle of each ring and expect 10 down to 1."""
    geo = _geometry(PRECISION_25M)
    seen = []
    for ring in range(10, 0, -1):
        outer = geo.ring_radius_mm(ring)
        inner = geo.ring_radius_mm(ring + 1) if ring < 10 else 0.0
        middle = (outer + inner) / 2
        seen.append(ring_for(_at_mm(middle, geo), geo, caliber_mm=0.001))
    assert seen == [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]


# --- The rule that makes this non-trivial: scoring by the bullet edge ---


def test_hole_touching_the_line_scores_the_higher_ring() -> None:
    """A shot centred outside ring 10 still scores 10 if the hole touches it.

    Ring 10 has a 25 mm radius on this target. A 9 mm bullet centred at 29 mm
    reaches inward to 29 - 4.5 = 24.5 mm, which is inside the line.
    """
    geo = _geometry(PRECISION_25M)
    assert ring_for(_at_mm(29.0, geo), geo, caliber_mm=9.0) == 10


def test_the_same_shot_with_a_smaller_calibre_scores_lower() -> None:
    """Identical position, .22 instead of 9 mm: the hole no longer reaches in.

    29 - 2.8 = 26.2 mm, outside ring 10's 25 mm radius. This is exactly why the
    caliber has to be recorded, and why one sheet with two calibers cannot be
    scored with a single value.
    """
    geo = _geometry(PRECISION_25M)
    assert ring_for(_at_mm(29.0, geo), geo, caliber_mm=5.6) == 9


def test_a_shot_just_outside_ring_one_is_saved_by_its_calibre() -> None:
    geo = _geometry(PRECISION_25M)
    # Ring 1 radius is 250 mm; a .45 centred at 255 mm reaches 249.25 mm.
    assert ring_for(_at_mm(255.0, geo), geo, caliber_mm=11.5) == 1


def test_negative_distance_is_treated_as_a_radius() -> None:
    geo = _geometry(PRECISION_25M)
    assert ring_for(-_at_mm(29.0, geo), geo, caliber_mm=9.0) == 10


# --- Air rifle: the hard case ---


def test_air_rifle_ten_is_smaller_than_the_pellet() -> None:
    """The 10 ring is 0.5 mm across and the pellet is 4.5 mm.

    Any pellet whose centre is within ~2.5 mm of the middle touches the 10 ring,
    which is exactly why automatic scoring of air rifle is a suggestion and not
    an answer — see ml/NOTES-real-targets.md.
    """
    geo = _geometry(AIR_RIFLE)
    assert geo.ring_radius_mm(10) == pytest.approx(0.25)
    assert ring_for(_at_mm(2.4, geo), geo) == 10
    assert ring_for(_at_mm(2.8, geo), geo) == 9


def test_air_rifle_outer_ring() -> None:
    geo = _geometry(AIR_RIFLE)
    # Ring 1 outer radius 22.75 mm; a pellet centred at 24 mm reaches 21.75.
    assert ring_for(_at_mm(24.0, geo), geo) == 1
    assert ring_for(_at_mm(26.0, geo), geo) == 0


# --- Inner ten ---


def test_inner_ten_is_stricter_than_a_ten() -> None:
    geo = _geometry(PRECISION_25M)
    # Inner ten radius 12.5 mm. A 9 mm bullet at 16 mm reaches 11.5 mm — inside.
    assert is_inner_ten(_at_mm(16.0, geo), geo, caliber_mm=9.0) is True
    # At 20 mm it reaches 15.5 mm — a ten, but not an inner ten.
    assert is_inner_ten(_at_mm(20.0, geo), geo, caliber_mm=9.0) is False
    assert ring_for(_at_mm(20.0, geo), geo, caliber_mm=9.0) == 10


# --- Series scoring ---


def test_score_series_totals_the_rings() -> None:
    geo = _geometry(PRECISION_25M)
    shots = [ShotInput(x=0.0, y=0.0) for _ in range(5)]
    result = score_series(shots, geo, caliber_mm=9.0)
    assert result.total == 50
    assert result.rings == [10, 10, 10, 10, 10]
    assert result.inner_tens == 5


def test_a_shot_may_override_the_series_calibre() -> None:
    """Two members, two calibers, one sheet — the case from the range."""
    geo = _geometry(PRECISION_25M)
    position = _at_mm(29.0, geo)
    result = score_series(
        [
            ShotInput(x=position, y=0.0),  # series default, 9 mm → 10
            ShotInput(x=position, y=0.0, caliber_mm=5.6),  # .22 → 9
        ],
        geo,
        caliber_mm=9.0,
    )
    assert result.rings == [10, 9]
    assert [s.caliber_mm for s in result.shots] == [9.0, 5.6]


def test_series_falls_back_to_the_targets_default_calibre() -> None:
    geo = _geometry(PRECISION_25M)
    result = score_series([ShotInput(x=_at_mm(29.0, geo), y=0.0)], geo)
    assert result.shots[0].caliber_mm == geo.default_caliber_mm


def test_empty_series_scores_zero() -> None:
    geo = _geometry(PRECISION_25M)
    result = score_series([], geo)
    assert result.total == 0
    assert result.grouping_mm is None


# --- Grouping ---


def test_grouping_is_outside_to_outside() -> None:
    geo = _geometry(PRECISION_25M)
    # Two shots 100 mm apart, 9 mm each → 100 + 4.5 + 4.5 = 109 mm.
    offset = _at_mm(50.0, geo)
    result = score_series(
        [ShotInput(x=-offset, y=0.0), ShotInput(x=offset, y=0.0)],
        geo,
        caliber_mm=9.0,
    )
    assert result.grouping_mm == pytest.approx(109.0)


def test_grouping_uses_each_shots_own_calibre() -> None:
    geo = _geometry(PRECISION_25M)
    offset = _at_mm(50.0, geo)
    result = score_series(
        [
            ShotInput(x=-offset, y=0.0, caliber_mm=9.0),
            ShotInput(x=offset, y=0.0, caliber_mm=5.6),
        ],
        geo,
    )
    assert result.grouping_mm == pytest.approx(100 + 4.5 + 2.8)


def test_grouping_ignores_a_shot_that_missed_the_sheet() -> None:
    """A wild shot says how badly it went, not how tight the group is.

    It has no measured position either — nobody looked at a hole, the shooter
    reported that one went off the paper — so letting it into the group size
    would swamp a measure that is otherwise in millimetres. The Android client
    drops it at the same boundary (`ScoringEngineTest`); the two engines
    disagreeing about a stored number is what this pair of tests prevents.
    """
    geo = _geometry(PRECISION_25M)
    offset = _at_mm(50.0, geo)
    tight = [ShotInput(x=-offset, y=0.0), ShotInput(x=offset, y=0.0)]
    with_miss = [*tight, ShotInput(x=0.0, y=1.4)]

    assert score_series(with_miss, geo, caliber_mm=9.0).grouping_mm == pytest.approx(109.0)

    # It is still a shot, and it is still scored — as a zero.
    scored = score_series(with_miss, geo, caliber_mm=9.0)
    assert len(scored.shots) == 3
    assert scored.shots[-1].ring == 0


def test_grouping_needs_two_shots() -> None:
    geo = _geometry(PRECISION_25M)
    assert grouping_mm([], geo) is None
    single = score_series([ShotInput(x=0.0, y=0.0)], geo)
    assert single.grouping_mm is None


# --- Geometry invariants ---


def test_geometry_rejects_the_wrong_number_of_rings() -> None:
    with pytest.raises(ValueError, match="10 ring diameters"):
        TargetGeometry(
            slug="broken",
            ring_diameters_mm=(10.0, 20.0),
            inner_ten_diameter_mm=5.0,
            black_diameter_mm=10.0,
            default_caliber_mm=4.5,
        )


def test_geometry_rejects_unsorted_rings() -> None:
    """Guards against the ordering mistake that made the iOS tables wrong."""
    with pytest.raises(ValueError, match="must increase"):
        TargetGeometry(
            slug="backwards",
            ring_diameters_mm=(500, 450, 400, 350, 300, 250, 200, 150, 100, 50),
            inner_ten_diameter_mm=25.0,
            black_diameter_mm=200.0,
            default_caliber_mm=9.0,
        )


@pytest.mark.parametrize("entry", TARGET_TYPES, ids=lambda e: str(e["slug"]))
def test_every_seeded_target_is_self_consistent(entry: dict) -> None:  # type: ignore[type-arg]
    """The seeds themselves are the thing most likely to be wrong.

    Wrong ring tables are why the earlier iOS prototype produced bad scores, so
    the file gets checked rather than trusted: ten rings, strictly increasing,
    inner ten no larger than ring 10, black inside the scoring area.
    """
    geo = TargetGeometry(
        slug=str(entry["slug"]),
        ring_diameters_mm=tuple(float(d) for d in entry["ring_diameters_mm"]),
        inner_ten_diameter_mm=float(entry["inner_ten_diameter_mm"]),
        black_diameter_mm=float(entry["black_diameter_mm"]),
        default_caliber_mm=float(entry["caliber_diameter_mm"]),
    )
    assert geo.inner_ten_diameter_mm <= geo.ring_diameters_mm[0]
    assert geo.black_diameter_mm <= geo.ring_diameters_mm[-1]
    assert geo.ring_fraction(1) == pytest.approx(1.0)
    # A shot dead centre must score 10 on every target.
    assert ring_for(0.0, geo) == 10


def test_diagonal_distance_is_euclidean() -> None:
    """Coordinates are cartesian; the ring depends on the radius, not on x or y."""
    geo = _geometry(PRECISION_25M)
    radius = _at_mm(100.0, geo)
    straight = score_series([ShotInput(x=radius, y=0.0)], geo, caliber_mm=9.0)
    diagonal_component = radius / math.sqrt(2)
    diagonal = score_series(
        [ShotInput(x=diagonal_component, y=diagonal_component)], geo, caliber_mm=9.0
    )
    assert straight.rings == diagonal.rings
