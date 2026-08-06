"""Checks `detect_hits.py` against synthetic targets whose shots are known.

Real photos say whether it works; only a rendered scene says by how much it is
off, because only there is it known where the shots actually were. The scenes
carry the two things that make the job hard on a real sheet (NOTES §1, §8):

  * far more patches than shots, over the black and over the paper, each with
    the thin darker seam its edge casts — the one thing on a sheet besides a
    hole that is darker than its surroundings,
  * shots on the black and shots on the paper, where a hole looks nothing alike.

For how the detector does on real sheets, run `score_hits.py`, which scores it
against hand-checked holes in actual photos. That number is the one that counts;
this one is what keeps a refactor honest.

Run: .venv/bin/python scripts/test_detect_hits.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from detect_hits import find_hits, tone_anchors  # noqa: E402
from rectify import downscale, find_aiming_mark, find_sheet, rectify  # noqa: E402
from test_rectify import render_target  # noqa: E402

#: A report and a shot this far apart are the same shot. Half a hole.
MATCH_MM = 5.0


def detect(scene: np.ndarray, size: int = 1280) -> list:
    """The whole chain a photo goes through: locate, rectify, find holes."""
    gray, scale = downscale(scene)
    fit = find_aiming_mark(gray, find_sheet(gray))
    if fit is None:
        return []
    for key in ("cx", "cy", "major", "minor"):
        setattr(fit, key, getattr(fit, key) / scale)
    crop = rectify(scene, fit, size=size)
    ink, paper = tone_anchors(crop)
    return find_hits(crop, ink, paper)


def score(found: list, truth: list[tuple[float, float]]) -> tuple[int, int, float]:
    """Matched, spurious, worst offset — closest pair first, one match each."""
    pairs = sorted(
        (math.hypot(hit.x_mm - x, hit.y_mm - y), f, t)
        for f, hit in enumerate(found)
        for t, (x, y) in enumerate(truth)
    )
    taken_found: set[int] = set()
    taken_truth: set[int] = set()
    worst = 0.0
    for distance, f, t in pairs:
        if distance > MATCH_MM or f in taken_found or t in taken_truth:
            continue
        taken_found.add(f)
        taken_truth.add(t)
        worst = max(worst, distance)
    return len(taken_found), len(found) - len(taken_found), worst


def roll(points: list[tuple[float, float]], degrees: float) -> list[tuple[float, float]]:
    """Turn truth positions by the camera roll of the scene.

    Rectification undoes the squash of an oblique photo but NOT the roll: the
    crop comes out turned by however the camera was held, and so do the shot
    coordinates. It costs the ring value nothing — that is a radius — but a shot
    picture drawn from these coordinates is rotated as a whole. Normalising it
    would belong in rectify.py, off the sheet's own edges; until it is there,
    this is what the numbers mean.
    """
    theta = math.radians(degrees)
    cos, sin = math.cos(theta), math.sin(theta)
    return [(x * cos - y * sin, x * sin + y * cos) for x, y in points]


def check(
    name: str,
    tolerance_mm: float,
    allow_missing: int = 0,
    allow_spurious: int = 0,
    **scene_args: object,
) -> bool:
    scene, truth = render_target(**scene_args)  # type: ignore[arg-type]
    found = detect(scene)
    truth["shots_mm"] = roll(truth["shots_mm"], float(scene_args.get("rotate_deg", 0.0)))
    matched, spurious, worst = score(found, truth["shots_mm"])
    missing = len(truth["shots_mm"]) - matched

    ok = (
        missing <= allow_missing
        and spurious <= allow_spurious
        and (worst <= tolerance_mm or matched == 0)
    )
    print(f"  {'ok  ' if ok else 'FAIL'} {name}: {matched}/{len(truth['shots_mm'])} found, "
          f"{spurious} spurious, worst off by {worst:.1f} mm "
          f"(allowed {tolerance_mm:.1f})")
    return ok


def check_patches_are_not_shots() -> bool:
    """A sheet covered in patches and not shot at all must report nothing.

    The case that matters most in the club: after every series the holes are
    patched, so most sheets a phone sees have forty patches and no fresh hole.
    Anything reported here would be reported on every one of them.
    """
    scene, _ = render_target(shots=0, patches=45)
    found = detect(scene)
    ok = not found
    print(f"  {'ok  ' if ok else 'FAIL'} patched, unshot: {len(found)} reported, want 0")
    return ok


def check_shots_on_paper() -> bool:
    """Holes outside the black, where a hole is a dark dot on white."""
    outside = tuple((math.cos(a) * 150.0, math.sin(a) * 150.0)
                    for a in (0.3, 1.9, 3.4, 5.0))
    scene, truth = render_target(shots=0, patches=25, extra_shots_mm=outside)
    matched, spurious, worst = score(detect(scene), truth["shots_mm"])
    ok = matched == len(outside) and spurious == 0
    print(f"  {'ok  ' if ok else 'FAIL'} shots on paper: {matched}/{len(outside)} found, "
          f"{spurious} spurious, worst off by {worst:.1f} mm")
    return ok


def check_touching_shots() -> bool:
    """Two 9 mm holes 7 mm apart are one dark region and still two shots.

    The other shots in the scene are not decoration: how far apart two holes
    have to be to be two holes is taken from the holes on the sheet that needed
    no splitting, so a sheet whose only mark is the pair cannot be read.

    Under about 6 mm of separation they merge for good — a 9 mm pair that close
    overlaps by nearly half and leaves one single ridge to find a centre on.
    """
    pair = ((30.0, -20.0), (37.0, -20.0))
    scene, truth = render_target(shots=3, patches=20, seed=4, extra_shots_mm=pair)
    found = detect(scene)
    matched, spurious, worst = score(found, truth["shots_mm"])
    ok = matched == len(truth["shots_mm"]) and spurious == 0
    print(f"  {'ok  ' if ok else 'FAIL'} two touching shots: {matched}/"
          f"{len(truth['shots_mm'])} found, {spurious} spurious, "
          f"worst off by {worst:.1f} mm")
    return ok


def check_diabolo() -> bool:
    """4.5 mm air rifle holes, the smallest thing there is to see.

    Rendered at 3.4 pixels per millimetre, roughly what a phone photo of a sheet
    filling the frame gives. It is the resolution of the PHOTO that decides this
    and not the crop: at 2 px/mm the black middle of a diabolo hole is under
    2 mm across and every one of the six is dropped, and no crop size puts back
    detail the photo never had. Air rifle therefore wants the sheet filling the
    viewfinder — NOTES §9, from the other end.
    """
    scene, truth = render_target(size=2400, shots=6, patches=20, shot_mm=4.5, seed=3)
    matched, spurious, _ = score(detect(scene), truth["shots_mm"])
    ok = matched == 6 and spurious == 0
    print(f"  {'ok  ' if ok else 'FAIL'} 4.5 mm holes: {matched}/6 found, "
          f"{spurious} spurious")
    return ok


def check_survives_exposure() -> bool:
    """The same scene under and over exposed must give the same shots.

    Every threshold is a fraction of the sheet's own ink and paper levels, so
    scaling the whole image cancels out — which is what lets one set of numbers
    work across cameras and light. What it does NOT survive is a raised black
    level, from haze or flare: that shifts ink and hole by the same amount
    rather than scaling them, and a hole then reads as a larger fraction of the
    ink. A tone measured against the ink-to-paper SPAN would be immune to it,
    and was tried — on the labelled photos it separated holes from patch seams
    distinctly worse, so the ratio stayed.
    """
    scene, truth = render_target(shots=6, patches=25, seed=11)
    counts = []
    for gain in (0.55, 1.0, 1.4):
        adjusted = np.clip(scene.astype(np.float32) * gain, 0, 255).astype(np.uint8)
        matched, spurious, _ = score(detect(adjusted), truth["shots_mm"])
        counts.append((matched, spurious))
    ok = len(set(counts)) == 1 and counts[0][1] == 0
    print(f"  {'ok  ' if ok else 'FAIL'} dark / normal / bright: "
          + " ".join(f"{m}+{s}" for m, s in counts)
          + f", want the same three times of {len(truth['shots_mm'])} shots")
    return ok


def main() -> int:
    print("Synthetic targets with known shots:")
    results = [
        check("square on        ", tolerance_mm=1.5),
        check("oblique + rolled ", tolerance_mm=1.5, tilt_deg=25.0, rotate_deg=10.0),
        # One pair in this scene lands 5 mm apart — two 9 mm holes overlapping
        # by nearly half, which merge into one and are reported as one.
        check("crowded sheet    ", tolerance_mm=3.0, allow_missing=1,
              patches=45, shots=10, seed=5),
        check_patches_are_not_shots(),
        check_shots_on_paper(),
        check_touching_shots(),
        check_diabolo(),
        check_survives_exposure(),
    ]
    passed = sum(results)
    print(f"\n{passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
