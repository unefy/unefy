"""Finds fresh shot holes in a rectified target crop — without a neural net.

Runs on the output of `rectify.py`, where a pixel is a known number of
millimetres and the target sits in a fixed frame. See NOTES-real-targets.md §8
for the observation this is built on, and `test_detect_hits.py` for what it is
held to.

Why local contrast, and what makes a hole a hole:

    Absolute brightness cannot separate a hole from anything else. The black
    aiming mark sits around 60 on real photos and so does a hole punched through
    white paper, so any single threshold either swallows the whole mark or
    misses half the hits. What does separate them is LOCAL contrast — a blob
    against its own ring of neighbours — plus one physical fact:

        a hole is darker than the target's own print.

    The black of the mark and the black of the printed digits are the same ink;
    a hole is a shadow into the backstop behind the sheet, and measures far
    darker than ink under the same light. Measured on IMG_1560: hole core 5-9,
    ink 56-68, paper 205, patches 190 on paper and 56-67 inside the mark.

    Both anchors — ink and paper — are read off the crop itself, from areas too
    large for shots or patches to shift: the mark's own annulus and the paper
    between the mark and ring 1. Exposure therefore cancels out; the thresholds
    below are ratios, not brightness values.

That also disposes of patches without ever having to recognise one. A patch is
a grey sticker: on paper it is barely darker than the paper, inside the mark it
is lighter than the mark. Neither is darker than ink, so neither survives. There
is no `patch` class here, and no model.

On 74 hand-checked holes in eleven real photos this reports 97.4 % precision at
100 % recall (`score_hits.py`, `data/hits-truth.json`). Where it stops:

  * Two holes overlapping by more than about half a diameter leave no waist
    between them and are reported as one.
  * A fresh hole cannot be told from an old unpatched one. Nothing in a single
    photo can — the club patches after every series, and that is the whole
    signal (NOTES §1).
  * The caliber is not read. What is reported is the diameter of the hole's
    dark core, which is what a two-caliber split works from (NOTES §1b).
  * A raised black level — haze, flare, a photo through glass — breaks the
    assumption that exposure cancels out. Plain under- or overexposure does not.

Usage:
    python scripts/detect_hits.py --input ~/Documents/Scheiben --report
    python scripts/detect_hits.py --input ~/Documents/Scheiben --overlay out/
    python scripts/detect_hits.py --input data/rectified --rectified --json hits.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from rectify import (  # noqa: E402
    CROP_SIZE,
    IMAGE_SUFFIXES,
    SCORING_MM,
    locate,
    px_per_mm,
    rectify,
)

#: Where the ink anchor is read: an annulus well inside the aiming mark, clear
#: of the light ring-10 core and of the mark's own edge.
INK_ANNULUS_MM = (35.0, 85.0)

#: Where the paper anchor is read: outside the mark, inside ring 1.
PAPER_ANNULUS_MM = (115.0, 230.0)

#: How dark a pixel must be, as a fraction of the ink level, to be part of a
#: hole at all. Generous: it decides how far a hole's torn rim is followed, and
#: what survives is decided afterwards on the core.
MASK_TONE = 0.55

#: How dark a blob's CORE must be, as a fraction of the ink level, to count as a
#: hole. Ink lands at 1.0 by construction and real holes well under it.
#:
#: Two thresholds, because what a hole has to be told apart from depends on
#: where it sits. On the black mark the competition is the seam between two
#: overlapping patches, which is dark, so the bar is high: measured over 142
#: photos, the cut sits in an empty stretch of the tone distribution (see
#: `--tones`). On paper nothing printed is darker than ink at all, and holes
#: there read greyer because what shows through them is the backstop rather than
#: shadow — 0.38 to 0.40 on IMG_0698 — so the same strict bar would throw them
#: away for nothing.
MAX_HOLE_TONE = 0.35
MAX_HOLE_TONE_ON_PAPER = 0.60

#: How much darker than its surroundings a candidate has to be, as a fraction of
#: the distance from ink to paper. Only there to keep sensor noise and paper
#: texture out — the real work is done by the tone test above. A fraction and
#: not a fixed number of levels: on a photo taken in poor light the whole scale
#: shrinks, and 20 levels that are nothing on a bright sheet are most of a hole
#: on a dark one.
MIN_CONTRAST_SPAN = 0.10

#: Hole sizes worth considering, in millimetres — of the DARK CORE, which is
#: what gets measured and which reads well under the caliber: paper springs back
#: around the projectile, and only the part that is properly black makes the
#: mask. Measured on this corpus: 7.2 mm of core for a 9 mm hole, 3.1 mm for
#: what is almost certainly .22, and under 2 mm for a grey, half-closed hole in
#: paper. The floor is therefore nowhere near the 4.5 mm of a diabolo — at
#: 1.6 mm every hole in hits-truth.json is found, at 2.0 mm three are lost, and
#: under 1.3 mm precision starts falling away (score_hits.py). The ceiling sits
#: above .45 for a badly torn one.
#:
#: The core is measured against a fixed fraction of the ink level, so it is the
#: same measurement on paper as on the black — which is what makes it usable for
#: telling two calibers on one sheet apart (NOTES §1b). It is a size ORDER, not
#: a caliber in millimetres, and nothing should treat it as one.
MIN_HOLE_MM = 1.6
MAX_HOLE_MM = 14.0

#: Smallest seed worth keeping, in pixels. Sensor noise and paper fibres make
#: two- and three-pixel specks; the black middle of even a diabolo hole is
#: larger than this.
MIN_SEED_PX = 8

#: How far apart two hole centres have to be, in multiples of the measured core
#: radius of a hole on the same sheet, to be two holes rather than one torn one.
#: The core reads about three quarters of the caliber, so 1.8 core radii is a
#: little under three quarters of a real diameter. Below that pairs start being
#: cut out of single torn holes: at 1.5 the labelled photos gained a false hole
#: and no real one (score_hits.py), and past about half a diameter of overlap
#: there is no waist left to find either way.
PITCH = 1.8

#: How much bigger than a hole on this sheet a blob may be before it is taken
#: for two holes that touch rather than one hole.
OVERSIZE = 1.5

#: How round a single hole has to be (4·pi·area / perimeter², 1.0 = a circle).
#: Torn paper is not smooth, so this is loose; it is here to reject the printed
#: ring lines, which are arcs and score far below it.
MIN_ROUNDNESS = 0.45

#: Nothing is looked for outside ring 1. The crop reaches past it, but so does
#: the sheet's edge and the backstop behind it, and neither is a shot.
SEARCH_MM = SCORING_MM / 2


@dataclass
class Hit:
    """One hole, in millimetres from the centre of the target."""

    x_mm: float
    y_mm: float
    #: Diameter of the hole's dark core — see MIN_HOLE_MM. Reads under the
    #: caliber, but comparably so across a sheet, which is what the two-caliber
    #: split needs (NOTES §1b).
    diameter_mm: float
    distance_mm: float
    #: Core brightness over the ink level. Near 0 is a clean hole, 1.0 is print.
    tone: float
    #: Core against its ring of neighbours, in 8-bit levels.
    contrast: float
    #: True when the hole was cut out of a cluster of touching holes, where the
    #: centre is an estimate and the diameter is not to be trusted.
    overlapping: bool = False


@dataclass
class Detection:
    image: str
    ok: bool
    hits: list[Hit]
    reason: str | None = None
    ink: float | None = None
    paper: float | None = None


def _disk(diameter_px: float) -> np.ndarray:
    size = max(3, int(diameter_px) | 1)
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


def _radius_map(size: int) -> np.ndarray:
    """Distance of every pixel from the crop's centre, in pixels."""
    axis = np.arange(size, dtype=np.float32) - (size - 1) / 2.0
    return np.sqrt(axis[None, :] ** 2 + axis[:, None] ** 2)


def tone_anchors(crop: np.ndarray) -> tuple[float, float]:
    """The brightness of the target's own ink and of its paper, in this photo.

    Medians over two large annuli: shots and patches are a minority inside both,
    and a median does not care about a minority. Everything downstream is
    measured against these two numbers, which is what makes the thresholds
    survive a change of light, camera or exposure.
    """
    scale = px_per_mm(crop.shape[0])
    radius = _radius_map(crop.shape[0])

    def band(inner_mm: float, outer_mm: float) -> float:
        mask = (radius >= inner_mm * scale) & (radius <= outer_mm * scale)
        return float(np.median(crop[mask]))

    return band(*INK_ANNULUS_MM), band(*PAPER_ANNULUS_MM)


def local_contrast(crop: np.ndarray) -> np.ndarray:
    """How much darker each pixel is than its own surroundings.

    Closing with a disk wider than any hole paints the hole over with whatever
    it sits on — mark, paper or an old patch — so the difference is the hole's
    depth alone, with the background subtracted out. Everything after this works
    on depth rather than on brightness, which is what lets one set of thresholds
    hold on black and on white at once.
    """
    scale = px_per_mm(crop.shape[0])
    blurred = cv2.GaussianBlur(crop, (3, 3), 0)
    closed = cv2.morphologyEx(blurred, cv2.MORPH_CLOSE, _disk(1.4 * MAX_HOLE_MM * scale))
    return cv2.subtract(closed, blurred)


def dark_mask(
    crop: np.ndarray, ink: float, paper: float, contrast: np.ndarray
) -> np.ndarray:
    """Seeds: pixels that are both darker than ink and darker than neighbours.

    Deliberately strict. It is not the hole — it is the part of the hole nothing
    else could explain, and `_grow` expands it to the real edge afterwards.
    """
    scale = px_per_mm(crop.shape[0])
    blurred = cv2.GaussianBlur(crop, (3, 3), 0)

    floor = MIN_CONTRAST_SPAN * (paper - ink)
    mask = ((contrast >= floor) & (blurred <= ink * MASK_TONE)).astype(np.uint8)
    mask *= 255

    # Only inside ring 1, and only after an opening that removes single-pixel
    # speckle without eating a 3 mm diabolo hole. A closing to knit the
    # fragments of a torn hole together was tried here as well and changed
    # nothing that hits-truth.json could see, so it is not in the code.
    mask[_radius_map(crop.shape[0]) > SEARCH_MM * scale] = 0
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, _disk(0.6 * scale))


def _measure(crop: np.ndarray, blob: np.ndarray) -> tuple[float, float]:
    """Brightness of a blob's core, and of the ring of neighbours around it."""
    core = cv2.erode(blob, _disk(3))
    if cv2.countNonZero(core) < 4:
        core = blob
    grown = cv2.dilate(blob, _disk(9))
    ring = cv2.subtract(cv2.dilate(grown, _disk(11)), grown)

    # The median, and not something lower. A torn hole has flaps of paper
    # standing up inside it that catch the light and pull its median towards
    # grey, so the 25th percentile looked like the fairer statistic — measured
    # against hits-truth.json it found nothing the paper threshold did not
    # already find, and cost two false positives (score_hits.py).
    inner = float(np.median(crop[core > 0]))
    outer = float(np.median(crop[ring > 0])) if cv2.countNonZero(ring) else inner
    return inner, outer


def _split(
    blob: np.ndarray, expected_r: float, min_radius: float
) -> list[tuple[float, float, float]]:
    """Pull the individual holes out of a clump of touching ones.

    Two holes 7 mm apart are one connected region, and reporting that as one big
    hole loses a shot and invents a nonsense size. The distance transform peaks
    where a hole is roundest and deepest, so its local maxima are the candidate
    centres and the peak value is that hole's radius.

    How close two peaks may be before they are one torn hole rather than two
    comes from `expected_r`, the size of a hole on THIS sheet, taken from the
    ones that needed no splitting. A fixed distance cannot do that job: the same
    clump is one .45 hole or three diabolo holes depending on the caliber.

    The limit is geometric, not a matter of tuning. Past roughly half a diameter
    of overlap there is no waist left between two holes, and they are then
    indistinguishable from one larger hole — for this and for anything else.
    """
    pitch = PITCH * expected_r
    dist = cv2.distanceTransform(blob, cv2.DIST_L2, 5)
    peaks = (dist >= cv2.dilate(dist, _disk(pitch)) - 1e-3) & (dist >= min_radius)

    count, _, _, centroids = cv2.connectedComponentsWithStats(peaks.astype(np.uint8), 8)
    candidates = []
    for index in range(1, count):
        x, y = centroids[index]
        candidates.append((float(x), float(y), float(dist[int(round(y)), int(round(x))])))

    # Widest first, and drop whatever falls inside a hole already taken.
    found: list[tuple[float, float, float]] = []
    for x, y, radius in sorted(candidates, key=lambda p: -p[2]):
        if any(np.hypot(x - px, y - py) < pitch for px, py, _ in found):
            continue
        found.append((x, y, radius))
    return found


def find_hits(
    crop: np.ndarray,
    ink: float | None = None,
    paper: float | None = None,
    max_tone: float | None = None,
) -> list[Hit]:
    """Every hole in the scoring area of a rectified crop.

    `max_tone` overrides both tone limits at once, and exists for the threshold
    sweep in `--tones`, which has to see the candidates they would drop.
    """
    scale = px_per_mm(crop.shape[0])
    centre = (crop.shape[0] - 1) / 2.0
    if ink is None or paper is None:
        ink, paper = tone_anchors(crop)
    on_mark_limit = max_tone if max_tone is not None else MAX_HOLE_TONE
    on_paper_limit = max_tone if max_tone is not None else MAX_HOLE_TONE_ON_PAPER
    #: Above this the blob sits on paper rather than on the black.
    paper_side = (ink + paper) / 2

    mask = dark_mask(crop, ink, paper, local_contrast(crop))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    # First pass: everything that already looks like one hole. A single hole is
    # round enough and no wider than a .45; anything else is either several
    # holes that touch — a pair 5 mm apart is one connected region, and pairs
    # are what a good series produces — or not a hole at all.
    singles: list[tuple[np.ndarray, float, float, float, float, float]] = []
    clumps: list[tuple[np.ndarray, float, float]] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < MIN_SEED_PX:
            continue
        diameter = 2.0 * np.sqrt(area / np.pi) / scale
        if diameter < MIN_HOLE_MM:
            continue

        blob = np.zeros(crop.shape, np.uint8)
        cv2.drawContours(blob, [contour], -1, 255, cv2.FILLED)
        inner, outer = _measure(crop, blob)
        tone = inner / ink if ink > 0 else 1.0
        contrast = outer - inner
        if tone > (on_paper_limit if outer >= paper_side else on_mark_limit):
            continue

        perimeter = cv2.arcLength(contour, True)
        roundness = 4 * np.pi * area / (perimeter * perimeter) if perimeter else 0.0
        if diameter <= MAX_HOLE_MM and roundness >= MIN_ROUNDNESS:
            moments = cv2.moments(contour)
            singles.append((blob, moments["m10"] / moments["m00"],
                            moments["m01"] / moments["m00"],
                            diameter / 2 * scale, tone, contrast))
        else:
            clumps.append((blob, tone, contrast))

    # How big a hole is on this sheet, from the ones nothing had to be assumed
    # about. It is what the splitter needs, and it is why the same clump can be
    # one torn .45 hole here and three diabolo holes there.
    if singles:
        expected_r = float(np.median([radius for _, _, _, radius, _, _ in singles]))
    else:
        expected_r = MIN_HOLE_MM * scale
    min_radius = MIN_HOLE_MM / 2 * scale

    # Two holes side by side make a shape that is still round enough to have
    # passed as one, and only its size gives it away. A blob half again the size
    # of a hole on this sheet therefore goes back to the splitter, which either
    # finds two centres in it or hands it back unchanged.
    found = []
    for blob, x, y, radius, tone, contrast in singles:
        if radius > OVERSIZE * expected_r and len(_split(blob, expected_r, min_radius)) > 1:
            clumps.append((blob, tone, contrast))
        else:
            found.append((x, y, radius, tone, contrast, False))

    for blob, tone, contrast in clumps:
        parts = _split(blob, expected_r, min_radius)
        found.extend((x, y, radius, tone, contrast, len(parts) > 1) for x, y, radius in parts)

    hits: list[Hit] = []
    for x, y, radius_px, tone, contrast, overlapping in found:
        hole_mm = 2 * radius_px / scale
        if not (MIN_HOLE_MM <= hole_mm <= MAX_HOLE_MM):
            continue
        dx, dy = (x - centre) / scale, (y - centre) / scale
        hits.append(
            Hit(
                x_mm=round(dx, 2),
                y_mm=round(dy, 2),
                diameter_mm=round(hole_mm, 2),
                distance_mm=round(float(np.hypot(dx, dy)), 2),
                tone=round(tone, 3),
                contrast=round(contrast, 1),
                overlapping=overlapping,
            )
        )

    hits.sort(key=lambda h: h.distance_mm)
    return hits


def annotate(crop: np.ndarray, hits: list[Hit]) -> np.ndarray:
    """The crop with every hit ringed, for looking at with human eyes."""
    scale = px_per_mm(crop.shape[0])
    centre = (crop.shape[0] - 1) / 2.0
    canvas = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)

    for index, hit in enumerate(hits, start=1):
        x = int(round(centre + hit.x_mm * scale))
        y = int(round(centre + hit.y_mm * scale))
        colour = (0, 165, 255) if hit.overlapping else (0, 0, 255)
        cv2.circle(canvas, (x, y), int(round(hit.diameter_mm / 2 * scale)) + 6, colour, 2)
        cv2.putText(canvas, str(index), (x + 12, y - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)

    cv2.putText(canvas, f"{len(hits)} hits", (16, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
    return canvas


def crop_for(path: Path, already_rectified: bool, size: int) -> np.ndarray | None:
    if already_rectified:
        return cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    located = locate(path)
    if located is None:
        return None
    full, fit = located
    return rectify(full, fit, size=size)


def process(
    path: Path,
    overlay_dir: Path | None,
    already_rectified: bool,
    size: int,
    max_tone: float = MAX_HOLE_TONE,
) -> Detection:
    try:
        crop = crop_for(path, already_rectified, size)
    except Exception as error:  # noqa: BLE001 — the report wants the reason
        return Detection(path.name, ok=False, hits=[], reason=str(error))
    if crop is None:
        return Detection(path.name, ok=False, hits=[], reason="no target found")

    ink, paper = tone_anchors(crop)
    if paper - ink < 30:
        # Ink and paper indistinguishable: the crop is not a target, or the
        # photo is so flat that no threshold on it would mean anything.
        return Detection(path.name, ok=False, hits=[], reason="no ink/paper contrast",
                         ink=ink, paper=paper)

    hits = find_hits(crop, ink, paper, max_tone)
    if overlay_dir is not None:
        overlay_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(overlay_dir / f"{path.stem}.png"), annotate(crop, hits))
    return Detection(path.name, ok=True, hits=hits, ink=ink, paper=paper)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="photos or crops")
    parser.add_argument("--rectified", action="store_true",
                        help="inputs are already rectified crops")
    parser.add_argument("--overlay", type=Path, default=None,
                        help="write annotated crops here")
    parser.add_argument("--json", type=Path, default=None, help="write results as JSON")
    parser.add_argument("--report", action="store_true", help="print a summary")
    parser.add_argument("--crop-size", type=int, default=CROP_SIZE)
    parser.add_argument("--limit", type=int, default=0, help="0 = all")
    parser.add_argument("--tones", action="store_true",
                        help="keep every candidate and print the tone histogram, "
                             "the evidence MAX_HOLE_TONE is chosen from")
    args = parser.parse_args()

    images = sorted(
        p for p in args.input.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES
    )
    if args.limit:
        images = images[: args.limit]
    if not images:
        print(f"No images under {args.input}")
        return

    max_tone = MASK_TONE if args.tones else MAX_HOLE_TONE
    results = [
        process(path, args.overlay, args.rectified, args.crop_size, max_tone)
        for path in images
    ]

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps([asdict(r) for r in results], indent=2))

    if args.tones:
        tones = np.array([h.tone for r in results for h in r.hits])
        print(f"\nTone of {tones.size} candidates, core over ink "
              f"(print = 1.0, hole ≈ 0.1):")
        edges = np.arange(0, MASK_TONE + 0.05, 0.05)
        counts, _ = np.histogram(tones, bins=edges)
        for low, count in zip(edges, counts):
            bar = "#" * int(60 * count / max(counts.max(), 1))
            print(f"  {low:4.2f}-{low + 0.05:4.2f} {count:5d} {bar}")
        print(f"\n  current cut at {MAX_HOLE_TONE}: keeps "
              f"{int((tones <= MAX_HOLE_TONE).sum())}, drops "
              f"{int((tones > MAX_HOLE_TONE).sum())}")
        return

    if not args.report:
        return

    ok = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    counts = [len(r.hits) for r in ok]
    print(f"\n{len(ok)}/{len(results)} crops analysed, "
          f"{sum(counts)} holes in {sum(1 for c in counts if c)} of them")

    if counts:
        counts_sorted = sorted(counts)
        print(f"  holes per target: median {counts_sorted[len(counts) // 2]}, "
              f"max {counts_sorted[-1]}, none on {counts.count(0)} targets")
        every = [h for r in ok for h in r.hits]
        if every:
            tone = np.array([h.tone for h in every])
            size = np.array([h.diameter_mm for h in every])
            print(f"  tone vs ink:  median {np.median(tone):.2f}  worst {tone.max():.2f} "
                  f"(print would be 1.0)")
            print(f"  diameter mm:  median {np.median(size):.1f}  "
                  f"p10 {np.percentile(size, 10):.1f}  p90 {np.percentile(size, 90):.1f}")
            print(f"  from clusters: {sum(1 for h in every if h.overlapping)}")

    if failed:
        print(f"\n{len(failed)} failed:")
        for r in failed[:20]:
            print(f"  {r.image}: {r.reason}")
        if len(failed) > 20:
            print(f"  … and {len(failed) - 20} more")


if __name__ == "__main__":
    main()
