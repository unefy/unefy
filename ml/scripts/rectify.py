"""Find the target in a photo, rectify it, and report how well that worked.

Run this over a folder of real photos BEFORE writing any on-device code. It
answers three questions that would otherwise only surface in the finished app:

1. Does the segmentation hold across your target types, lighting and cameras?
2. How oblique are real photos — does the orthographic approximation carry, or
   is the full homography needed from the start?
3. Which images fail, and why?

It is also the reference the Kotlin `TargetLocator` will be cross-checked
against, and it produces the rectified crops that the hit detector is annotated
and trained on. See ml/NOTES-real-targets.md for what real sheets look like.

The method, and why it is not a neural network:

    A circle photographed at an angle is an ellipse. The black aiming mark is
    the highest-contrast feature on any target and its physical diameter is
    known exactly per target type. Fitting an ellipse to its outer edge yields
    centre, scale (px→mm) and perspective in one step — deterministically, with
    no training data. ML is for telling holes from patches, later, on the
    rectified crop.

Two details that real photos forced (both in NOTES-real-targets.md):

    * The aiming mark is an ANNULUS: ring 10 is printed light inside it. The fit
      must use the OUTER contour — fitting the inner one is wrong by a factor of
      four in scale.
    * The backstop behind the target is itself full of dark bullet holes, and
      there are dark surfaces all around. A global threshold happily finds those
      instead, which is why the search is restricted to the largest bright
      quadrilateral (the sheet) when one can be found.

Usage:
    python scripts/rectify.py --input ~/scheiben --out data/rectified --report
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import cv2
import numpy as np

#: Longest edge the analysis runs at. Full-resolution phone photos cost time and
#: buy nothing: the aiming mark is hundreds of pixels across either way.
WORK_SIZE = 1024

#: Side length of the rectified crop. Square, centred on the target, so every
#: image the detector ever sees is in the same frame.
#:
#: 1600 and not 640: at 640 a 9 mm hole is ten pixels across and a 4.5 mm
#: diabolo five — too little for the hit detector and for a human placing a shot
#: by hand (NOTES-real-targets.md §9). The crop is warped from the ORIGINAL
#: photo, not from the downscaled working copy, so those pixels carry real
#: detail instead of interpolation.
#:
#: 1472 over a 1.15 frame is 2.56 pixels per millimetre, and that RESOLUTION is
#: what actually matters — it was picked by scoring the hit detector at each size
#: against hits-truth.json. Coarser loses holes; FINER loses precision, because
#: paper grain and JPEG noise start resolving into blobs the size of a small
#: hole. Both directions were measured (score_hits.py). So when the frame below
#: changed from 1.25 to 1.15 this had to follow it, or the crop would silently
#: have become finer at 2.78.
CROP_SIZE = 1472

#: How much of the scoring radius the crop covers. Over 1.0 so that ring 1 and
#: the paper around it stay inside the frame.
#:
#: 1.15 puts the frame at 575 mm across, which sits ENTIRELY within a 600 mm
#: sheet: no backstop in the crop, whatever is behind the target. At 1.25 the
#: frame was 625 mm and a strip of whatever the sheet hangs on was in every
#: picture — 12 mm a side by construction, and more once the sheet is tilted.
#: Ring 1 ends at 500 mm, so nothing scoreable is lost.
#:
#: Must equal `TargetGeometry.FRAME_TO_SCORING` in the Android app, which draws
#: its rings in the same frame and lays this crop underneath them. They were
#: 1.15 here and 1.25 there once already, which quietly meant the reference
#: implementation and the app were measuring different pictures.
CROP_MARGIN = 1.15

#: Diameter of the scoring area — ring 1 — of the target being scanned. The
#: crop is scaled so this fits it, which is what makes a crop pixel a known
#: number of millimetres (see `px_per_mm`).
SCORING_MM = 500.0

#: Aiming mark diameter as a fraction of ring 1, for the target being scanned.
#: Scheibe Nr. 5: 200 mm black on a 500 mm scoring area.
#:
#: The fit measures the MARK, but the crop has to frame the whole SCORING AREA —
#: scaling straight off the mark cropped everything outside ring 6 away, taking
#: real hits with it. Different targets have different ratios (air rifle is
#: 30.5/45.5), which is why it is a parameter and not a constant.
DEFAULT_BLACK_RATIO = 200.0 / SCORING_MM

#: Below this the ellipse is too oblique for the orthographic approximation and
#: the shot positions start to drift. Mirrors the app's warning threshold.
OBLIQUE_WARN = 0.80

#: Plausible aiming mark diameter as a fraction of the sheet's width. Wide
#: enough for every standard target (Scheibe Nr. 5 sits near 0.36, air rifle
#: near 0.18) and narrow enough to reject the backstop behind the sheet.
MIN_MARK_OF_SHEET = 0.08
MAX_MARK_OF_SHEET = 0.65

#: How far the paper's brightness may fall before the sheet is taken to have
#: ended. Well below the paper, because a sheet is never evenly lit; well above
#: the grey of a backstop.
SHEET_EDGE_OF_PAPER = 0.72

#: How many directions the sheet's edge is probed in, and how far out — in
#: multiples of the aiming mark's radius. The sheet measures three mark radii to
#: its edge and 4.2 to its corners, so five leaves room for an oblique photo.
SHEET_RAYS = 180
SHEET_REACH = 5.0

#: A ray that got much further than the rest went through a gap in the edge. The
#: corners of a square legitimately reach 1.41 times the edge distance, so the
#: bar has to sit above that or it cuts the corners off — measured, that alone
#: shrank the sheet by eight per cent.
SHEET_RAY_TRIM = 1.7

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".bmp"}


@dataclass
class TargetFit:
    """Where the target is in the (downscaled) image."""

    cx: float
    cy: float
    #: Semi-axes in pixels, major first.
    major: float
    minor: float
    #: Rotation of the MAJOR axis in degrees — not OpenCV's raw `fitEllipse`
    #: angle, which describes the width axis whether or not that is the longer.
    angle: float
    #: minor/major. 1.0 is dead-on; lower means more oblique.
    circularity: float
    #: How the mark was found, for the report.
    method: str

    @property
    def oblique(self) -> bool:
        return self.circularity < OBLIQUE_WARN


@dataclass
class Result:
    image: str
    ok: bool
    reason: str | None = None
    fit: dict | None = None  # type: ignore[type-arg]


def px_per_mm(size: int = CROP_SIZE, scoring_mm: float = SCORING_MM) -> float:
    """Pixels per millimetre in a rectified crop of the given side length."""
    return size / (CROP_MARGIN * scoring_mm)


def load_full(path: Path) -> np.ndarray:
    """Read an image at its original resolution, as grayscale."""
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("unreadable")
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def downscale(gray: np.ndarray) -> tuple[np.ndarray, float]:
    """The working copy of an image, and the factor it was scaled by."""
    longest = max(gray.shape[:2])
    scale = WORK_SIZE / longest if longest > WORK_SIZE else 1.0
    if scale == 1.0:
        return gray, 1.0
    return cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA), scale


def load_gray(path: Path) -> tuple[np.ndarray, float]:
    """Read an image, downscale it, return grayscale and the scale factor."""
    return downscale(load_full(path))


def locate(path: Path) -> tuple[np.ndarray, TargetFit] | None:
    """Find the target, and hand back the ORIGINAL photo alongside the fit.

    Searching runs on the downscaled copy — the aiming mark is hundreds of
    pixels across either way — but the crop must be warped from the full
    resolution, or the extra pixels of a large crop are interpolation rather
    than detail. The returned fit is therefore expressed in the original's pixels.
    """
    full = load_full(path)
    gray, scale = downscale(full)
    fit = find_aiming_mark(gray, find_sheet(gray))
    if fit is None:
        # The sheet mask can be wrong (bright wall, overexposed backstop).
        # Worth one retry without it before calling the image a failure.
        fit = find_aiming_mark(gray, None)
    if fit is None:
        return None

    if scale != 1.0:
        fit = replace(
            fit,
            cx=fit.cx / scale,
            cy=fit.cy / scale,
            major=fit.major / scale,
            minor=fit.minor / scale,
        )
    return full, fit


def find_sheet(gray: np.ndarray) -> np.ndarray | None:
    """The bright paper as a mask, if a plausible one stands out.

    Not for measuring — sheet formats vary by manufacturer while the aiming mark
    is standardised, so the SCALE always comes from the mark. This only narrows
    where to look, which is what keeps a bullet-riddled backstop from winning.
    """
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    level, bright = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # A second split, over the bright side only. One Otsu pass separates
    # "target and backstop" from "dark surroundings" — and the backstop is a
    # grey foam board, so it lands on the bright side together with the paper.
    # It is darker than the paper though, which makes it the largest dark region
    # inside the mask, and the ellipse fit then locks onto the backstop instead
    # of the aiming mark. Splitting the bright side again isolates the paper.
    upper = blurred[blurred >= level]
    if upper.size > 0:
        paper_level, _ = cv2.threshold(upper, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        refined = np.zeros_like(gray)
        refined[blurred >= paper_level] = 255
        # Only trust it if a decent sheet remains; on a photo with no backstop
        # in frame the second split can eat the target itself.
        if cv2.countNonZero(refined) > 0.06 * gray.size:
            bright = refined

    bright = cv2.morphologyEx(
        bright, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
    )

    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    frame_area = float(gray.shape[0] * gray.shape[1])
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < 0.10 * frame_area:
        return None

    mask = np.zeros_like(gray)
    # Filled convex hull: the sheet is punched full of holes and often creased,
    # and the holes must not become part of the boundary.
    cv2.drawContours(mask, [cv2.convexHull(largest)], -1, 255, thickness=cv2.FILLED)
    return mask


def find_aiming_mark(gray: np.ndarray, sheet: np.ndarray | None) -> TargetFit | None:
    """Fit an ellipse to the outer edge of the black aiming mark."""
    region = gray if sheet is None else cv2.bitwise_and(gray, gray, mask=sheet)
    method = "sheet+mark" if sheet is not None else "mark-only"

    # Threshold only over the sheet's own pixels; including the dark surroundings
    # drags Otsu's split into the wrong place.
    values = region[sheet > 0] if sheet is not None else gray.reshape(-1)
    if values.size == 0:
        return None
    level, _ = cv2.threshold(values, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    dark = np.zeros_like(gray)
    dark[(gray < level) & (sheet > 0 if sheet is not None else True)] = 255
    dark = cv2.morphologyEx(
        dark, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    )

    # RETR_EXTERNAL is the point: ring 10 is printed light inside the mark, so
    # the region is a ring. Only its outer boundary has the known diameter.
    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    candidates = [c for c in contours if len(c) >= 5 and cv2.contourArea(c) > 500]
    if not candidates:
        return None

    # How wide the aiming mark may plausibly be, measured against the sheet.
    # Without this a blob larger than the entire sheet was accepted: on 29 of the
    # first 142 real photos the fit sat on the backstop, 1.56x the sheet's own
    # width, and nothing objected.
    if sheet is not None:
        ys, xs = np.where(sheet > 0)
        sheet_width = float(xs.max() - xs.min()) if xs.size else float(gray.shape[1])
    else:
        sheet_width = float(min(gray.shape))
    max_major = MAX_MARK_OF_SHEET * sheet_width / 2.0
    min_major = MIN_MARK_OF_SHEET * sheet_width / 2.0

    best: tuple[float, TargetFit] | None = None
    for contour in candidates:
        (cx, cy), (width, height), angle = cv2.fitEllipse(contour)

        # `angle` describes the WIDTH axis. When the height is the longer one the
        # major axis is ninety degrees away, and taking `angle` regardless (as an
        # earlier version did) stretches across the squash instead of along it —
        # rectification then made oblique photos worse, not better.
        if height >= width:
            major, minor, major_angle = height / 2.0, width / 2.0, angle + 90.0
        else:
            major, minor, major_angle = width / 2.0, height / 2.0, angle
        if major <= 0 or minor <= 0:
            continue

        circularity = minor / major
        area = cv2.contourArea(contour)
        ellipse_area = math.pi * major * minor
        if ellipse_area <= 0:
            continue

        # How well the blob actually is an ellipse. A shadow or a dark corner
        # can be fitted too; it just fits badly.
        fill = area / ellipse_area
        if fill < 0.75 or circularity < 0.35:
            continue
        if not (min_major <= major <= max_major):
            continue

        score = fill * area
        fit = TargetFit(cx, cy, major, minor, major_angle, circularity, method)
        if best is None or score > best[0]:
            best = (score, fit)

    return best[1] if best else None


def sheet_quad(gray: np.ndarray, fit: TargetFit) -> np.ndarray | None:
    """The four corners of the sheet, for the viewfinder's outline.

    Walks outward from the aiming mark and stops where the paper stops. Two
    other ways were measured over 142 club photographs, with the sheet's own
    geometry as the yardstick — the mark is standardised, so half the sheet's
    width divided by the mark's radius is a constant of the printed sheet, and
    it is 3.00 for these:

        brightness threshold   2.68   systematically 11 % short
        Canny + contours       3.76   and found a sheet in only 25 of 142
        rays from the mark     3.02

    The threshold falls short because it is a threshold: the lower part of a
    sheet is nearly always in shadow, the global split puts it on the wrong
    side, and the outline then cuts straight across the target. Edges do not
    care about a shadow, which is what document scanners rely on — but a
    scanner has to find a sheet in an unknown scene, and by this point we
    already know exactly where the target is and how big. Starting from it is
    both simpler and better.
    """
    height, width = gray.shape

    # Paper, sampled just outside the mark where the sheet certainly is.
    ring = []
    for index in range(64):
        angle = 2.0 * math.pi * index / 64
        x = int(fit.cx + math.cos(angle) * fit.major * 1.3)
        y = int(fit.cy + math.sin(angle) * fit.major * 1.3)
        if 0 <= x < width and 0 <= y < height:
            ring.append(gray[y, x])
    if not ring:
        return None
    edge_level = float(np.median(ring)) * SHEET_EDGE_OF_PAPER

    points = []
    for index in range(SHEET_RAYS):
        angle = 2.0 * math.pi * index / SHEET_RAYS
        dx, dy = math.cos(angle), math.sin(angle)
        last = None
        distance = fit.major * 1.3
        while distance < fit.major * SHEET_REACH:
            x, y = int(fit.cx + dx * distance), int(fit.cy + dy * distance)
            if not (0 <= x < width and 0 <= y < height):
                break
            if gray[y, x] < edge_level:
                # Only a step that STAYS down is the edge. A shadow falls off
                # again; the background does not.
                ahead = [
                    gray[int(fit.cy + dy * (distance + k)), int(fit.cx + dx * (distance + k))]
                    for k in range(2, 12)
                    if 0 <= int(fit.cx + dx * (distance + k)) < width
                    and 0 <= int(fit.cy + dy * (distance + k)) < height
                ]
                if ahead and float(np.median(ahead)) < edge_level:
                    break
            last = (x, y)
            distance += 2
        if last is not None:
            points.append(last)

    if len(points) < 20:
        return None
    found = np.array(points, dtype=np.int32)
    radii = np.hypot(found[:, 0] - fit.cx, found[:, 1] - fit.cy)
    kept = found[radii < SHEET_RAY_TRIM * np.median(radii)]
    if len(kept) < 20:
        kept = found

    hull = cv2.convexHull(kept).reshape(-1, 2)
    total, difference = hull.sum(axis=1), hull[:, 0] - hull[:, 1]
    return np.array([
        hull[total.argmin()],       # top left
        hull[difference.argmax()],  # top right
        hull[total.argmax()],       # bottom right
        hull[difference.argmin()],  # bottom left
    ])


def rectify(
    gray: np.ndarray,
    fit: TargetFit,
    size: int = CROP_SIZE,
    black_ratio: float = DEFAULT_BLACK_RATIO,
) -> np.ndarray:
    """Map the ellipse back to a circle and crop around the centre.

    An affine un-squash, not a full homography: for radial distance — which is
    all the ring lookup needs — undoing the ellipse is enough as long as the
    photo is not wildly oblique. `circularity` is reported so that assumption
    can be checked against real data rather than assumed.
    """
    scale_minor = fit.major / fit.minor
    theta = math.radians(fit.angle)
    cos, sin = math.cos(theta), math.sin(theta)

    # Rotate the major axis onto x, stretch the short axis back to circular,
    # rotate back, then centre the result in the output.
    rotate = np.array([[cos, sin], [-sin, cos]], dtype=np.float64)
    stretch = np.array([[1.0, 0.0], [0.0, scale_minor]], dtype=np.float64)
    linear = rotate.T @ stretch @ rotate

    # Where ring 1 should land in the output, converted back to what that means
    # for the mark the fit actually measured.
    scoring_radius_out = size / (2.0 * CROP_MARGIN)
    linear *= (scoring_radius_out * black_ratio) / fit.major

    offset = np.array([size / 2.0, size / 2.0]) - linear @ np.array([fit.cx, fit.cy])
    matrix = np.hstack([linear, offset.reshape(2, 1)]).astype(np.float32)
    return cv2.warpAffine(gray, matrix, (size, size), flags=cv2.INTER_LINEAR)


def process(
    path: Path,
    out_dir: Path | None,
    black_ratio: float = DEFAULT_BLACK_RATIO,
    size: int = CROP_SIZE,
) -> Result:
    try:
        located = locate(path)
    except Exception as error:  # noqa: BLE001 — the report wants the reason
        return Result(path.name, ok=False, reason=str(error))
    if located is None:
        return Result(path.name, ok=False, reason="no aiming mark found")
    full, fit = located

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(
            str(out_dir / f"{path.stem}.png"),
            rectify(full, fit, size=size, black_ratio=black_ratio),
        )

    # Coordinates are in the ORIGINAL image's pixels, not the downscaled
    # working copy — anything consuming this works on the original.
    return Result(path.name, ok=True, fit=asdict(fit))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="folder of photos")
    parser.add_argument("--out", type=Path, default=None, help="where to write crops")
    parser.add_argument("--report", action="store_true", help="print a summary")
    parser.add_argument("--json", type=Path, default=None, help="write results as JSON")
    parser.add_argument(
        "--black-ratio",
        type=float,
        default=DEFAULT_BLACK_RATIO,
        help="aiming mark diameter / ring 1 diameter (default: Scheibe Nr. 5)",
    )
    parser.add_argument(
        "--crop-size", type=int, default=CROP_SIZE, help="side length of the crops"
    )
    args = parser.parse_args()

    images = sorted(
        p for p in args.input.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES
    )
    if not images:
        print(f"No images under {args.input}")
        return

    results = [
        process(path, args.out, args.black_ratio, args.crop_size) for path in images
    ]

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps([asdict(r) for r in results], indent=2))

    if not args.report:
        return

    ok = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    print(f"\n{len(ok)}/{len(results)} targets located ({len(ok) / len(results):.0%})")

    if ok:
        circ = sorted(r.fit["circularity"] for r in ok if r.fit)
        oblique = [c for c in circ if c < OBLIQUE_WARN]

        def pct(p: float) -> float:
            return circ[min(int(p * len(circ)), len(circ) - 1)]

        print("\nHow square-on the photos are (minor/major, 1.0 = dead-on):")
        print(f"  worst {circ[0]:.2f} | p10 {pct(0.10):.2f} | median {pct(0.50):.2f} "
              f"| best {circ[-1]:.2f}")
        print(f"  below {OBLIQUE_WARN:.2f}: {len(oblique)}/{len(circ)} "
              f"({len(oblique) / len(circ):.0%}) — these need the full homography")

        by_method: dict[str, int] = {}
        for r in ok:
            if r.fit:
                by_method[r.fit["method"]] = by_method.get(r.fit["method"], 0) + 1
        print("\nFound via: " + ", ".join(f"{k} {v}" for k, v in sorted(by_method.items())))

    if failed:
        print(f"\n{len(failed)} failed:")
        for r in failed[:20]:
            print(f"  {r.image}: {r.reason}")
        if len(failed) > 20:
            print(f"  … and {len(failed) - 20} more")


if __name__ == "__main__":
    main()
