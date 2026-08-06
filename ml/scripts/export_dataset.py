"""Builds the training set for the hit detector: crops, plus labels to correct.

The model is trained on RECTIFIED crops rather than on raw photos, because the
geometry is already solved and solved well: `rectify.py` puts every sheet in the
same frame at a known scale (142/142 located, under a tenth of a ring of error).
A detector that has to learn "where is the target" as well would need far more
data to be no better. So the model gets one job — hole or not — on an image
where a pixel is always 0.39 mm.

Labels are written from `detect_hits.py`, which is right about 90 % of the time,
so annotating means correcting rather than drawing. Where a photo appears in
`data/hits-truth.json` the checked holes are used instead: 83 boxes that are
already known to be right, including the six that the rule-based detector
misses and that are the reason for training a model at all.

    python scripts/export_dataset.py --input ~/Documents/Scheiben

Then correct the labels — labelImg, Roboflow, whatever — and train:

    python scripts/split_dataset.py
    python scripts/train.py

The yardstick does not change: `score_hits.py` scores a model against the same
hand-checked holes it scores the rule-based detector against, so the comparison
is like for like. Anything else and the two are not comparable.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).parent))
from detect_hits import find_hits, tone_anchors  # noqa: E402
from rectify import (  # noqa: E402
    CROP_MARGIN,
    CROP_SIZE,
    IMAGE_SUFFIXES,
    SCORING_MM,
    locate,
    px_per_mm,
    rectify,
)

#: One class. Patches are not annotated: a detector learns "not a hole" from
#: everything it is not shown, and a sheet carries forty patches to eight holes —
#: annotating them would be six thousand boxes for a distinction the background
#: already teaches. If the model turns out to confuse the two, that is the moment
#: to spend the afternoon, not before.
CLASSES = ["hit"]

#: How much wider than the measured dark core a box is drawn. The core reads
#: about three quarters of the caliber (NOTES §8b2), and a box should cover the
#: torn rim as well, which is what a human annotator would draw.
BOX_OF_CORE = 1.8

#: Box size for a hole that came from the checked truth, which records positions
#: but no size. A 9 mm hole with its rim.
TRUTH_BOX_MM = 11.0

#: Quality for the crops. Lossless would be 1.3 MB a photo, 190 MB for the set.
JPEG_QUALITY = 95


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path.home() / "Documents/Scheiben")
    parser.add_argument("--out", type=Path, default=Path("data/dataset"))
    parser.add_argument("--truth", type=Path, default=Path("data/hits-truth.json"))
    parser.add_argument("--limit", type=int, default=0, help="0 = all")
    args = parser.parse_args()

    checked = {}
    if args.truth.exists():
        checked = json.loads(args.truth.read_text())["targets"]

    images_dir = args.out / "images"
    labels_dir = args.out / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    photos = sorted(p for p in args.input.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES)
    if args.limit:
        photos = photos[: args.limit]

    scale = px_per_mm(CROP_SIZE)
    from_truth = from_detector = failed = 0
    boxes = 0

    for photo in photos:
        located = locate(photo)
        if located is None:
            failed += 1
            continue
        crop = rectify(*located, size=CROP_SIZE)
        cv2.imwrite(
            str(images_dir / f"{photo.stem}.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        )

        entry = checked.get(photo.stem)
        if entry is not None:
            holes = [(x, y, TRUTH_BOX_MM) for x, y in entry["holes"]]
            from_truth += 1
        else:
            ink, paper = tone_anchors(crop)
            holes = [
                (hit.x_mm, hit.y_mm, hit.diameter_mm * BOX_OF_CORE)
                for hit in find_hits(crop, ink, paper)
            ]
            from_detector += 1

        lines = []
        for x_mm, y_mm, size_mm in holes:
            # YOLO: class, centre and size as fractions of the image.
            cx = (CROP_SIZE / 2 + x_mm * scale) / CROP_SIZE
            cy = (CROP_SIZE / 2 + y_mm * scale) / CROP_SIZE
            side = max(size_mm, 4.0) * scale / CROP_SIZE
            if not (0 < cx < 1 and 0 < cy < 1):
                continue
            lines.append(f"0 {cx:.6f} {cy:.6f} {side:.6f} {side:.6f}")
        (labels_dir / f"{photo.stem}.txt").write_text("\n".join(lines) + "\n")
        boxes += len(lines)

    (args.out / "classes.txt").write_text("\n".join(CLASSES) + "\n")
    (args.out / "dataset.yaml").write_text(
        f"# Rectified crops: {CROP_SIZE} px across {CROP_MARGIN} scoring radii of a\n"
        f"# {SCORING_MM:.0f} mm target, so one pixel is {1 / scale:.3f} mm and a 9 mm\n"
        f"# hole is {9 * scale:.0f} px. Train at imgsz {CROP_SIZE} or the holes shrink\n"
        f"# below what a detector can see.\n"
        "path: ../data/dataset\n"
        "train: train/images\n"
        "val: val/images\n"
        f"names:\n" + "".join(f"  {i}: {name}\n" for i, name in enumerate(CLASSES))
    )

    print(f"\n{len(photos) - failed} crops written to {images_dir}")
    print(f"  {from_truth} labelled from hand-checked holes — correct already")
    print(f"  {from_detector} pre-labelled by detect_hits.py — these need correcting")
    print(f"  {boxes} boxes in total, {failed} photos where no target was found")
    print("\nCorrect the labels, then: python scripts/split_dataset.py && python scripts/train.py")


if __name__ == "__main__":
    main()
