"""Scores `detect_hits.py` against the hand-checked holes in hits-truth.json.

`--report` from the detector says how much it found. This says how much of it
was right, which is a different question and the only one worth tuning on: an
extra threshold always finds more, and usually finds more of the wrong thing.

Every number below moves in the opposite direction to another one, so read them
together:

    precision  of what it reported, how much is a real hole
    recall     of the real holes, how much it reported
    off by     how far the reported centre sits from the checked one

"off by" is the weakest of the three and reads better than it is: most checked
positions were taken from a detection that a human then confirmed, so the two
agree by construction. It only says something where the checked hole came from
somewhere else — two reports judged one hole, say. Position accuracy is measured
properly in `test_detect_hits.py`, on scenes where the shots were placed.

Run it after any change to the detector, before believing the change helped:

    python scripts/score_hits.py --input ~/Documents/Scheiben

The truth file is a labelled sample, not the whole corpus, and its holes were
picked out of a deliberately over-sensitive candidate pass — see the note inside
it for what that does and does not cover.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from detect_hits import Hit, crop_for, tone_anchors, find_hits  # noqa: E402

#: How far a reported hole may sit from a checked one and still be the same
#: hole. A shot is 5-9 mm across, so anything within half of that is plainly the
#: same hole and anything past a whole one plainly is not.
MATCH_MM = 6.0


def match(found: list[Hit], truth: list[list[float]]) -> list[tuple[int, int, float]]:
    """Pair reported holes with checked ones, closest pair first.

    Greedy on distance rather than in order: a hole is only ever claimed by its
    nearest report, so two reports on one hole leave the second unmatched — a
    double count has to show up as a false positive, not be absorbed.
    """
    pairs = sorted(
        (float(np.hypot(hit.x_mm - x, hit.y_mm - y)), f, t)
        for f, hit in enumerate(found)
        for t, (x, y) in enumerate(truth)
    )
    taken_found: set[int] = set()
    taken_truth: set[int] = set()
    matched = []
    for distance, f, t in pairs:
        if distance > MATCH_MM or f in taken_found or t in taken_truth:
            continue
        taken_found.add(f)
        taken_truth.add(t)
        matched.append((f, t, distance))
    return matched


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path.home() / "Documents/Scheiben")
    parser.add_argument("--truth", type=Path, default=Path("data/hits-truth.json"))
    parser.add_argument("--crop-size", type=int, default=1280)
    parser.add_argument("--per-image", action="store_true", help="one line per photo")
    args = parser.parse_args()

    truth_file = json.loads(args.truth.read_text())
    targets = truth_file["targets"]

    total_found = total_truth = total_hit = 0
    offsets: list[float] = []
    rows = []

    for name, entry in sorted(targets.items()):
        photo = next(
            (p for p in args.input.rglob(f"{name}.*") if p.suffix.lower() != ".json"), None
        )
        if photo is None:
            print(f"  {name}: photo not found under {args.input}")
            continue

        crop = crop_for(photo, already_rectified=False, size=args.crop_size)
        if crop is None:
            print(f"  {name}: no target found")
            continue
        ink, paper = tone_anchors(crop)
        found = find_hits(crop, ink, paper)

        matched = match(found, entry["holes"])
        offsets.extend(distance for _, _, distance in matched)

        # Reports that landed on something nobody could judge are set aside
        # rather than counted against the detector.
        unmatched = [f for f in range(len(found)) if f not in {m[0] for m in matched}]
        ignored = {f for f, _, _ in match([found[f] for f in unmatched], entry["unsure"])}
        spurious = len(unmatched) - len(ignored)

        total_found += len(found) - len(ignored)
        total_truth += len(entry["holes"])
        total_hit += len(matched)
        rows.append((name, len(entry["holes"]), len(matched), spurious,
                     len(entry["holes"]) - len(matched)))

    if not total_truth:
        print("No truth to score against.")
        return

    print(f"\n{len(rows)} photos, {total_truth} checked holes\n")
    if args.per_image:
        print(f"  {'image':<12} {'truth':>5} {'found':>5} {'extra':>5} {'missed':>6}")
        for name, truth_n, hit_n, extra, missed in rows:
            flag = "  <--" if extra or missed else ""
            print(f"  {name:<12} {truth_n:>5} {hit_n:>5} {extra:>5} {missed:>6}{flag}")
        print()

    precision = total_hit / total_found if total_found else 0.0
    recall = total_hit / total_truth
    print(f"  precision {precision:6.1%}   ({total_found - total_hit} reported holes "
          f"were not one)")
    print(f"  recall    {recall:6.1%}   ({total_truth - total_hit} checked holes "
          f"were not reported)")
    if offsets:
        off = np.array(offsets)
        print(f"  off by     {np.median(off):.2f} mm median, {off.max():.2f} mm worst")


if __name__ == "__main__":
    main()
