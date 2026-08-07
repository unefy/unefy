"""Turns shot positions into ring values. Pure geometry, no database.

The server recomputes every ring value it is sent. A client that scores its own
shots is convenient offline, but two clients disagreeing about a ring is a result
dispute, so the number that gets stored is always the one computed here. Where a
client's value differs, the caller logs it — that difference is the only warning
anybody gets that the Kotlin and Python engines have drifted apart.

Coordinate convention, shared with the mobile clients:

    x, y are normalised to the RING 1 RADIUS, origin at the target centre,
    y pointing down (screen coordinates). A shot at (0, 0) is dead centre;
    |(x, y)| == 1.0 sits exactly on the outer edge of ring 1.

Scoring is by the EDGE of the bullet hole, not its centre: a hole that merely
touches the line scores the higher ring. That single rule is why the caliber has
to be right — see `app.core.target_type_seeds.CALIBERS`.

The caliber is resolved per shot, in this order:

    shot.caliber_mm  →  series default  →  the target type's default

Two levels of override rather than one because a single sheet really does carry
two calibers — a club shoots .22 and 9 mm at the same target, and on the 25 m
target that is a ~1.7 mm difference in scoring radius, enough to change a ring.
"""

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

RING_COUNT = 10

#: How far past ring 1 the printed sheet reaches, in scoring radii. Shared with
#: `TargetGeometry.FRAME_TO_SCORING` in the Android app and with the rectified
#: crop in ml/scripts/rectify.py — the same frame everywhere, or a photo and the
#: rings drawn over it do not line up.
FRAME_TO_SCORING = 1.25


@dataclass(frozen=True)
class TargetGeometry:
    """Ring geometry in millimetres, independent of how it was loaded."""

    slug: str
    #: Outer diameters, index 0 = ring 10 … index 9 = ring 1.
    ring_diameters_mm: tuple[float, ...]
    inner_ten_diameter_mm: float
    black_diameter_mm: float
    default_caliber_mm: float

    @classmethod
    def from_model(cls, row: Any) -> "TargetGeometry":
        return cls(
            slug=row.slug,
            ring_diameters_mm=tuple(float(d) for d in row.ring_diameters_mm),
            inner_ten_diameter_mm=float(row.inner_ten_diameter_mm),
            black_diameter_mm=float(row.black_diameter_mm),
            default_caliber_mm=float(row.caliber_diameter_mm),
        )

    def __post_init__(self) -> None:
        if len(self.ring_diameters_mm) != RING_COUNT:
            raise ValueError(
                f"{self.slug}: expected {RING_COUNT} ring diameters, "
                f"got {len(self.ring_diameters_mm)}"
            )
        if list(self.ring_diameters_mm) != sorted(self.ring_diameters_mm):
            raise ValueError(f"{self.slug}: ring diameters must increase from ring 10 to ring 1")

    @property
    def scoring_radius_mm(self) -> float:
        """Radius of ring 1 — the reference length for normalised coordinates."""
        return self.ring_diameters_mm[-1] / 2.0

    def ring_radius_mm(self, ring: int) -> float:
        """Outer radius of `ring` in mm. Ring 10 is the innermost."""
        return self.ring_diameters_mm[RING_COUNT - ring] / 2.0

    def ring_fraction(self, ring: int) -> float:
        """Outer radius of `ring` as a fraction of the scoring radius (0…1)."""
        return self.ring_radius_mm(ring) / self.scoring_radius_mm


def ring_for(
    distance_normalized: float,
    geometry: TargetGeometry,
    caliber_mm: float | None = None,
) -> int:
    """Ring value for a shot at `distance_normalized` from the centre.

    Returns 0 for a miss (outside ring 1). Scoring is by the edge of the hole
    nearest the centre, so a shot whose centre lies outside a ring still scores
    it when the hole touches the line.
    """
    caliber = geometry.default_caliber_mm if caliber_mm is None else caliber_mm
    distance_mm = abs(distance_normalized) * geometry.scoring_radius_mm
    bullet_edge_mm = max(0.0, distance_mm - caliber / 2.0)

    for ring in range(RING_COUNT, 0, -1):
        if bullet_edge_mm <= geometry.ring_radius_mm(ring):
            return ring
    return 0


def is_inner_ten(
    distance_normalized: float,
    geometry: TargetGeometry,
    caliber_mm: float | None = None,
) -> bool:
    """Whether the shot counts as an inner ten (Innenzehner), for tiebreaks."""
    caliber = geometry.default_caliber_mm if caliber_mm is None else caliber_mm
    distance_mm = abs(distance_normalized) * geometry.scoring_radius_mm
    bullet_edge_mm = max(0.0, distance_mm - caliber / 2.0)
    return bullet_edge_mm <= geometry.inner_ten_diameter_mm / 2.0


def grouping_mm(
    shots: list["ScoredShot"],
    geometry: TargetGeometry,
) -> float | None:
    """Group size (Streukreis): widest outside-to-outside spread of the group.

    The conventional measure — largest centre-to-centre distance plus one
    caliber, i.e. how wide the group is from the outer edge of one hole to the
    outer edge of the furthest other. With mixed calibers on one sheet the two
    holes at the extremes may differ, so each contributes its own radius rather
    than assuming a single caliber. None for fewer than two shots.
    """
    # A shot that missed the sheet altogether says nothing about how tight the
    # group is — it only says one went wide, which the ring value already
    # records. Leaving it in would let a single flyer swamp the measure, and it
    # has no real position anyway: there is no hole to measure to.
    on_sheet = [s for s in shots if math.hypot(s.x, s.y) <= FRAME_TO_SCORING]
    if len(on_sheet) < 2:
        return None
    radius = geometry.scoring_radius_mm

    widest = 0.0
    for i, a in enumerate(on_sheet):
        for b in on_sheet[i + 1 :]:
            centre_to_centre = math.hypot(a.x - b.x, a.y - b.y) * radius
            widest = max(widest, centre_to_centre + a.caliber_mm / 2 + b.caliber_mm / 2)
    return round(widest, 2)


@dataclass(frozen=True)
class ShotInput:
    """One shot as the client reports it, before scoring."""

    x: float
    y: float
    #: Overrides the series default. Set when one sheet carries two calibers.
    caliber_mm: float | None = None


@dataclass(frozen=True)
class ScoredShot:
    x: float
    y: float
    ring: int
    inner_ten: bool
    #: The caliber actually used, after resolving the override chain. Stored so
    #: the score can be recomputed later without guessing.
    caliber_mm: float


@dataclass(frozen=True)
class SeriesScore:
    shots: list[ScoredShot]
    total: Decimal
    inner_tens: int
    grouping_mm: float | None

    @property
    def rings(self) -> list[int]:
        return [s.ring for s in self.shots]


def score_series(
    shots: list[ShotInput],
    geometry: TargetGeometry,
    caliber_mm: float | None = None,
) -> SeriesScore:
    """Score a whole series. `caliber_mm` is the series default; a shot may
    override it."""
    series_default = geometry.default_caliber_mm if caliber_mm is None else caliber_mm

    scored: list[ScoredShot] = []
    for shot in shots:
        effective = series_default if shot.caliber_mm is None else shot.caliber_mm
        distance = math.hypot(shot.x, shot.y)
        scored.append(
            ScoredShot(
                x=shot.x,
                y=shot.y,
                ring=ring_for(distance, geometry, effective),
                inner_ten=is_inner_ten(distance, geometry, effective),
                caliber_mm=effective,
            )
        )
    return SeriesScore(
        shots=scored,
        total=Decimal(sum(s.ring for s in scored)),
        inner_tens=sum(1 for s in scored if s.inner_ten),
        grouping_mm=grouping_mm(scored, geometry),
    )
