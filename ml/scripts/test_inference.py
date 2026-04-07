"""Test the trained model on a single image.

Shows detections with bounding boxes and class labels.

Usage:
    python scripts/test_inference.py path/to/image.jpg
    python scripts/test_inference.py path/to/image.jpg --model models/target_detector/weights/best.pt
"""

import argparse
from pathlib import Path

from ultralytics import YOLO

MODELS_DIR = Path(__file__).parent.parent / "models"
DEFAULT_WEIGHTS = MODELS_DIR / "target_detector" / "weights" / "best.pt"
CLASS_NAMES = {0: "target", 1: "target_center", 2: "hit_small", 3: "hit_medium", 4: "hit_large", 5: "hit_cluster", 6: "patch"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--model", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--conf", type=float, default=0.3, help="Confidence threshold")
    args = parser.parse_args()

    model = YOLO(str(args.model))
    results = model(str(args.image), conf=args.conf)

    for r in results:
        boxes = r.boxes
        print(f"\nDetections on {args.image.name}:")
        print(f"{'Class':<15} {'Conf':>6} {'X1':>6} {'Y1':>6} {'X2':>6} {'Y2':>6}")
        print("-" * 55)

        hits = []
        patches = []

        for box in boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            cls_name = CLASS_NAMES.get(cls_id, f"cls_{cls_id}")
            print(f"{cls_name:<15} {conf:>6.2f} {x1:>6.0f} {y1:>6.0f} {x2:>6.0f} {y2:>6.0f}")

            if cls_name == "hit":
                hits.append((conf, (x1 + x2) / 2, (y1 + y2) / 2))
            elif cls_name == "patch":
                patches.append((conf, (x1 + x2) / 2, (y1 + y2) / 2))

        print(f"\nSummary: {len(hits)} hits, {len(patches)} patches detected")

        # Save annotated image.
        output_path = args.image.parent / f"{args.image.stem}_detected{args.image.suffix}"
        r.save(filename=str(output_path))
        print(f"Annotated image: {output_path}")


if __name__ == "__main__":
    main()
