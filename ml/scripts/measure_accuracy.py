"""Measures how accurate the rectification is, against the printed rings.

There is no ground truth for "where was the centre really", so accuracy cannot
be checked directly. But there is an indirect check that costs nothing: in a
correctly rectified crop the target's own printed ring lines must sit at known
radii. Whatever they are off by is the error of the whole chain — sheet
detection, ellipse fit, scale, rectification.

Run it after any change to the locator. A regression shows up as a shifted
median (systematic) or a wider spread (unstable).

    python scripts/measure_accuracy.py --input data/rectified
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import cv2
import numpy as np

from rectify import CROP_MARGIN, SCORING_MM, px_per_mm

#: Scheibe Nr. 5: ring n has outer diameter (11-n)*50 mm, ring 1 is 500 mm.
RING_MM = {n: (11 - n) * 50.0 for n in range(1, 11)}

#: Rings measured. Only those outside the black mark are dark lines on light
#: paper; inside it they are light on dark and the profile inverts.
MEASURED_RINGS = (2, 3, 4, 5)

#: How far either side of the expected radius to look for the line. In
#: millimetres, so the measurement stays the same when the crop size changes —
#: half a ring width, which is as far as a line can be off before it would be
#: confused with its neighbour.
SEARCH_MM = 12.5


def scoring_px(size: int) -> float:
    """Radius of ring 1 in a crop of this side length."""
    return size / (2 * CROP_MARGIN)


def search_px(size: int) -> float:
    return SEARCH_MM * px_per_mm(size)


def radial_profile(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Median brightness at each radius. Ring lines show up as minima.

    A median across the circle rather than a mean: shot holes and patches are
    dark too, and a mean would let a handful of them pull the whole ring.
    """
    height, width = image.shape
    cx, cy = width / 2, height / 2
    radii = np.arange(10, int(scoring_px(height) * 1.02))
    angles = np.linspace(0, 2 * math.pi, 240, endpoint=False)

    profile = []
    for r in radii:
        values = []
        for a in angles:
            x, y = int(cx + math.cos(a) * r), int(cy + math.sin(a) * r)
            if 0 <= x < width and 0 <= y < height:
                values.append(image[y, x])
        profile.append(np.median(values) if values else np.nan)
    return radii, np.array(profile, dtype=float)


def errors_for(image: np.ndarray) -> list[float]:
    radii, profile = radial_profile(image)
    if np.isnan(profile).any():
        return []

    found = []
    search = search_px(image.shape[0])
    for ring in MEASURED_RINGS:
        expected = scoring_px(image.shape[0]) * (RING_MM[ring] / SCORING_MM)
        window = (radii > expected - search) & (radii < expected + search)
        if window.sum() < 8:
            continue
        line = radii[window][np.argmin(profile[window])]
        found.append((line - expected) / expected)
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/rectified"))
    parser.add_argument("--limit", type=int, default=0, help="0 = all")
    args = parser.parse_args()

    crops = sorted(args.input.glob("*.png"))
    if args.limit:
        crops = crops[: args.limit]
    if not crops:
        print(f"No crops under {args.input} — run rectify.py first.")
        return

    errors: list[float] = []
    for path in crops:
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is not None:
            errors.extend(errors_for(image))

    e = np.array(errors)
    if e.size == 0:
        print("No ring lines could be measured.")
        return

    # A ring is 25 mm wide on this target; that is the yardstick that matters.
    mm = e * (SCORING_MM / 2)
    print(f"{e.size} ring measurements from {len(crops)} crops\n")
    print(f"  radius error   median {np.median(e) * 100:+.2f}%   spread {e.std() * 100:.2f}%")
    print(f"  in millimetres median {np.median(mm):+.1f} mm    spread {mm.std():.1f} mm")
    print(f"  as a fraction of one 25 mm ring: {abs(np.median(mm)) / 25:.0%} median, "
          f"{mm.std() / 25:.0%} spread")


if __name__ == "__main__":
    main()
