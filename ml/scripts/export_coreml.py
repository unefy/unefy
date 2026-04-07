"""Export trained YOLOv8 model to Core ML for iOS.

Output: models/TargetDetector.mlpackage
Copy this into the iOS app's Resources/ folder.

Usage:
    python scripts/export_coreml.py
    python scripts/export_coreml.py --model models/target_detector/weights/best.pt
"""

import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO

MODELS_DIR = Path(__file__).parent.parent / "models"
DEFAULT_WEIGHTS = MODELS_DIR / "target_detector" / "weights" / "best.pt"
IOS_RESOURCES = (
    Path(__file__).parent.parent.parent
    / "apps" / "mobile" / "ios" / "unefy" / "Resources" / "MLModels"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--half", action="store_true", help="FP16 quantization")
    args = parser.parse_args()

    if not args.model.exists():
        print(f"Model not found: {args.model}")
        print("Run 'python scripts/train.py' first.")
        raise SystemExit(1)

    model = YOLO(str(args.model))

    # Export to Core ML.
    model.export(
        format="coreml",
        imgsz=args.imgsz,
        half=args.half,
        nms=True,  # include NMS in the model
    )

    # The export creates a .mlpackage next to the .pt file.
    exported = args.model.with_suffix(".mlpackage")
    if not exported.exists():
        # Sometimes it's in the parent directory.
        exported = args.model.parent / "best.mlpackage"

    if exported.exists():
        target = MODELS_DIR / "TargetDetector.mlpackage"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(exported, target)
        print(f"\nExported: {target}")
        print(f"Size: {sum(f.stat().st_size for f in target.rglob('*') if f.is_file()) / 1024 / 1024:.1f} MB")

        # Optionally copy to iOS app.
        if IOS_RESOURCES.parent.exists():
            ios_target = IOS_RESOURCES / "TargetDetector.mlpackage"
            IOS_RESOURCES.mkdir(parents=True, exist_ok=True)
            if ios_target.exists():
                shutil.rmtree(ios_target)
            shutil.copytree(target, ios_target)
            print(f"Copied to iOS: {ios_target}")
    else:
        print(f"Export file not found. Check {args.model.parent}")


if __name__ == "__main__":
    main()
