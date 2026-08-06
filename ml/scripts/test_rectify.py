"""Checks `rectify.py` against synthetic targets whose truth is known.

Real photos tell you whether it works in practice; they cannot tell you by how
much it is off, because nobody knows where the centre really was. Synthetic
scenes can: the target is rendered from a known centre, radius and viewing
angle, so the fit can be scored in pixels rather than eyeballed.

The scenes deliberately include what a real range photo has, and what broke
naive approaches (see NOTES-real-targets.md):

  * a dark backstop peppered with bullet holes — dark blobs that a global
    threshold will happily mistake for the aiming mark,
  * the aiming mark as an ANNULUS, ring 10 printed light inside it,
  * perspective, from square-on to distinctly oblique,
  * shot holes and patches on the sheet itself.

Run: .venv/bin/python scripts/test_rectify.py
"""

from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from rectify import find_aiming_mark, find_sheet, load_gray, rectify  # noqa: E402

# Scheibe Nr. 5, in millimetres. Ring 1 is 500 across, the black is 200,
# ring 10 — printed light inside the black — is 50.
RING_1_MM = 500.0
BLACK_MM = 200.0
RING_10_MM = 50.0
SHEET_MM = 550.0

SHEET_COLOR = 238
BLACK_COLOR = 30
BACKSTOP_COLOR = 70

#: A hole is a shadow into the backstop, and measures far darker than the ink of
#: the print — the fact `detect_hits.py` rests on (NOTES-real-targets.md §8).
HOLE_COLOR = 6

#: How much of a hole comes out properly black. Paper springs back around the
#: projectile and the torn rim only half shadows, so what is measurably dark is
#: a good bit smaller than the caliber: on real photos a 9 mm hole leaves about
#: 7 mm of black. Drawing holes as flat discs instead made the splitter look
#: better in tests than it is.
HOLE_CORE = 0.78
HOLE_RIM_COLOR = 90

#: A patch is a grey sticker: on paper a little darker than the paper, over the
#: black a little lighter than the black, and never anywhere near a hole. Its
#: edge casts a thin darker seam, which is the one thing on a real sheet that a
#: hole detector can plausibly mistake for a shot.
PATCH_ON_PAPER = 210
PATCH_ON_BLACK = 44
PATCH_SEAM = 20


def render_target(
    size: int = 1400,
    tilt_deg: float = 0.0,
    rotate_deg: float = 0.0,
    shots: int = 8,
    patches: int = 25,
    seed: int = 7,
    shot_mm: float = 9.0,
    extra_shots_mm: tuple[tuple[float, float], ...] = (),
) -> tuple[np.ndarray, dict]:
    """A target on a bullet-riddled backstop. Returns the image and its truth.

    `extra_shots_mm` places shots at exact positions in millimetres from the
    centre, on top of the random ones — for the cases where the position is the
    point, such as two holes close enough to touch.
    """
    rng = np.random.default_rng(seed)

    # --- backstop: dark, and full of dark holes that look like small marks ---
    scene = np.full((size, size), BACKSTOP_COLOR, dtype=np.uint8)
    for _ in range(220):
        x, y = rng.integers(0, size, 2)
        cv2.circle(scene, (int(x), int(y)), int(rng.integers(3, 11)), 20, -1)

    # --- the sheet, drawn flat and then projected ---
    flat = np.full((size, size), SHEET_COLOR, dtype=np.uint8)
    centre = size / 2.0
    px_per_mm = (size * 0.78) / SHEET_MM

    def radius(mm: float) -> int:
        return int(round(mm / 2.0 * px_per_mm))

    cv2.circle(flat, (int(centre), int(centre)), radius(BLACK_MM), BLACK_COLOR, -1)
    # Ring 10 light inside the black: this is what makes the mark an annulus.
    cv2.circle(flat, (int(centre), int(centre)), radius(RING_10_MM), SHEET_COLOR, -1)
    for ring in range(1, 11):
        mm = RING_1_MM * (11 - ring) / 10.0
        on_black = mm <= BLACK_MM
        cv2.circle(
            flat,
            (int(centre), int(centre)),
            radius(mm),
            220 if on_black else 90,
            1,
        )

    for _ in range(patches):
        angle, dist = rng.uniform(0, 2 * math.pi), rng.uniform(0.1, 0.9) * radius(RING_1_MM)
        p = (int(centre + math.cos(angle) * dist), int(centre + math.sin(angle) * dist))
        on_black = dist <= radius(BLACK_MM)
        colour = PATCH_ON_BLACK if on_black else PATCH_ON_PAPER
        cv2.circle(flat, p, int(round(5.0 * px_per_mm)), colour - PATCH_SEAM, -1)
        cv2.circle(flat, p, int(round(4.4 * px_per_mm)), colour, -1)

    shot_truth = []
    placed = [
        (rng.uniform(0, 2 * math.pi), rng.uniform(0.0, 0.45) * radius(RING_1_MM))
        for _ in range(shots)
    ]
    for angle, dist in placed:
        shot_truth.append((math.cos(angle) * dist / px_per_mm,
                           math.sin(angle) * dist / px_per_mm))
    shot_truth.extend(extra_shots_mm)
    for x_mm, y_mm in shot_truth:
        p = (int(round(centre + x_mm * px_per_mm)), int(round(centre + y_mm * px_per_mm)))
        cv2.circle(flat, p, int(round(shot_mm / 2 * px_per_mm)), HOLE_RIM_COLOR, -1)
        cv2.circle(flat, p, max(1, int(round(shot_mm * HOLE_CORE / 2 * px_per_mm))),
                   HOLE_COLOR, -1)

    sheet_half = radius(SHEET_MM)
    corners = np.float32([
        [centre - sheet_half, centre - sheet_half],
        [centre + sheet_half, centre - sheet_half],
        [centre + sheet_half, centre + sheet_half],
        [centre - sheet_half, centre + sheet_half],
    ])

    # Tilt about the vertical axis, then roll the camera.
    shrink = math.cos(math.radians(tilt_deg))
    target = corners.copy()
    target[:, 0] = centre + (target[:, 0] - centre) * shrink
    if rotate_deg:
        theta = math.radians(rotate_deg)
        cos, sin = math.cos(theta), math.sin(theta)
        rel = target - centre
        target = np.stack([
            centre + rel[:, 0] * cos - rel[:, 1] * sin,
            centre + rel[:, 0] * sin + rel[:, 1] * cos,
        ], axis=1).astype(np.float32)

    warp = cv2.getPerspectiveTransform(corners, target)
    warped = cv2.warpPerspective(
        flat, warp, (size, size), flags=cv2.INTER_LINEAR, borderValue=0
    )
    mask = cv2.warpPerspective(
        np.full((size, size), 255, np.uint8), warp, (size, size), flags=cv2.INTER_NEAREST
    )
    scene[mask > 0] = warped[mask > 0]

    black_major = radius(BLACK_MM)
    return scene, {
        "cx": centre,
        "cy": centre,
        "major": float(black_major),
        "minor": float(black_major * shrink),
        "circularity": shrink,
        #: Where the shots were put, in millimetres from the centre of the
        #: target — the truth `test_detect_hits.py` scores against.
        "shots_mm": [(round(x, 2), round(y, 2)) for x, y in shot_truth],
        "shot_mm": shot_mm,
    }


def check(name: str, tilt: float, rotate: float, tolerance_px: float) -> bool:
    scene, truth = render_target(tilt_deg=tilt, rotate_deg=rotate)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scene.png"
        cv2.imwrite(str(path), scene)
        gray, _ = load_gray(path)

    sheet = find_sheet(gray)
    fit = find_aiming_mark(gray, sheet)
    if fit is None:
        print(f"  FAIL {name}: no aiming mark found")
        return False

    # The truth is in full-size pixels; the fit works on the downscaled copy.
    scale = gray.shape[0] / scene.shape[0]
    dx = fit.cx / scale - truth["cx"]
    dy = fit.cy / scale - truth["cy"]
    centre_error = math.hypot(dx, dy)
    radius_error = abs(fit.major / scale - truth["major"]) / truth["major"]
    circ_error = abs(fit.circularity - truth["circularity"])

    ok = (
        centre_error <= tolerance_px
        and radius_error <= 0.05
        and circ_error <= 0.06
    )
    status = "ok  " if ok else "FAIL"
    print(
        f"  {status} {name}: centre off {centre_error:5.1f}px, "
        f"radius off {radius_error:5.1%}, circularity {fit.circularity:.2f} "
        f"(true {truth['circularity']:.2f}) via {fit.method}"
    )
    return ok


def check_rectified_is_round() -> bool:
    """After rectification the black mark must come back circular.

    The whole point: an oblique photo produces the same measurements as a
    square-on one, so the ring lookup does not have to care about the angle.
    """
    scene, _ = render_target(tilt_deg=35.0, rotate_deg=12.0)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scene.png"
        cv2.imwrite(str(path), scene)
        gray, _ = load_gray(path)

    fit = find_aiming_mark(gray, find_sheet(gray))
    if fit is None:
        print("  FAIL rectified: no aiming mark found")
        return False

    crop = rectify(gray, fit)
    refit = find_aiming_mark(crop, None)
    if refit is None:
        print("  FAIL rectified: mark lost after rectification")
        return False

    ok = refit.circularity >= 0.97
    print(
        f"  {'ok  ' if ok else 'FAIL'} rectified: circularity "
        f"{fit.circularity:.2f} -> {refit.circularity:.2f} (want >= 0.97)"
    )
    return ok


def main() -> int:
    print("Synthetic targets (Scheibe Nr. 5 on a bullet-riddled backstop):")
    results = [
        check("square on        ", 0.0, 0.0, tolerance_px=6),
        check("slightly oblique ", 15.0, 0.0, tolerance_px=8),
        check("oblique + rolled ", 30.0, 10.0, tolerance_px=12),
        check("strongly oblique ", 45.0, -18.0, tolerance_px=20),
        check_rectified_is_round(),
    ]
    passed = sum(results)
    print(f"\n{passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
