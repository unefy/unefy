"""Writes the rectified crops and hit positions the Kotlin tests check against.

The Android app carries its own implementations of what `rectify.py` and
`detect_hits.py` do, because shipping OpenCV to a phone costs 30 MB and a
16 KB-page-alignment problem. Two implementations of the same algorithm drift
apart silently, so the Kotlin side is held to what this one produces on real
photographs — the same arrangement the scoring engine already has with the
backend.

This exports the hit-detection half:

    ml/data/hits-truth.json  ->  crops + expected hits for HitDetectorTest

Only the photos that were checked by hand are exported, and only a few of them:
a fixture is a megabyte of PNG in the repository, so they are chosen to cover
the cases that behave differently rather than to be many. Run it after any
change to the detector that moves the reported positions, and look at the diff
— a fixture whose expected hits change is either a fix or a regression, and the
diff is where that gets decided.

    python scripts/export_fixtures.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).parent))
from detect_hits import find_hits, tone_anchors  # noqa: E402
from rectify import CROP_MARGIN, CROP_SIZE, locate, rectify  # noqa: E402

#: Which of the hand-checked photos become fixtures, and what each one is for.
FIXTURES = {
    "IMG_0684": "five clean holes in the black, patches around them",
    "IMG_1500": "holes in the black plus one patch that must not count",
    "IMG_1514": "a hole torn across the edge of a patch, and one full of flaps",
    "IMG_1528": "freshly patched, not a single fresh hole — must report none",
    "IMG_S25_0807": "bright backstop: holes read 0.36-0.40 of the ink, so this "
                    "one only scores at all if tone_slack is applied",
}

#: Quality the fixture crops are written at. High enough that the detector
#: reports the same holes as on the lossless crop, which is checked by running
#: score_hits.py before and after.
FIXTURE_QUALITY = 92

DEFAULT_OUT = Path(
    "../apps/mobile/android/core/model/src/test/resources/hits"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path.home() / "Documents/Scheiben")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--truth", type=Path, default=Path("data/hits-truth.json"))
    args = parser.parse_args()

    checked = json.loads(args.truth.read_text())["targets"]
    args.out.mkdir(parents=True, exist_ok=True)

    exported = []
    for name, why in sorted(FIXTURES.items()):
        photo = next(iter(args.input.glob(f"{name}.*")), None)
        if photo is None:
            print(f"  {name}: not found under {args.input}")
            continue
        located = locate(photo)
        if located is None:
            print(f"  {name}: no target found")
            continue

        # JPEG, not PNG: a lossless crop is 1.3 MB and four of them are five
        # megabytes of repository for one test. The expected hits are then read
        # back OUT of the JPEG, so both implementations see the same pixels and
        # the compression cannot put them out of step.
        path = args.out / f"{name}.jpg"
        cv2.imwrite(str(path), rectify(*located, size=CROP_SIZE),
                    [cv2.IMWRITE_JPEG_QUALITY, FIXTURE_QUALITY])
        crop = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)

        ink, paper = tone_anchors(crop)
        hits = find_hits(crop, ink, paper)
        exported.append({
            "image": f"{name}.jpg",
            "why": why,
            "hits": [
                # Millimetres from the centre, x right and y down — the frame
                # everything downstream of the detector speaks in.
                {"x_mm": hit.x_mm, "y_mm": hit.y_mm, "diameter_mm": hit.diameter_mm}
                for hit in hits
            ],
            "checked": len(checked.get(name, {}).get("holes", [])),
        })
        print(f"  {name}: {len(hits)} hits, {exported[-1]['checked']} checked by hand")

    (args.out / "expected.json").write_text(json.dumps({
        "note": (
            "Written by ml/scripts/export_fixtures.py. The crops are what "
            "rectify.py produces from the club photographs in "
            "~/Documents/Scheiben; the hits are what detect_hits.py finds in "
            "them. 'checked' is how many holes a human confirmed in that photo "
            "(ml/data/hits-truth.json) — where it differs from the number of "
            "hits, the Python side is known to be wrong by that much, and the "
            "Kotlin side is only asked to agree with Python."
        ),
        "crop_size": CROP_SIZE,
        "frame_to_scoring": CROP_MARGIN,
        "targets": exported,
    }, indent=1) + "\n")
    print(f"\nwrote {len(exported)} fixtures to {args.out}")


if __name__ == "__main__":
    main()
