"""Train YOLOv8 for shooting target detection.

Uses YOLOv8n (nano) as base — small enough for on-device inference
(~6MB model), fast enough for real-time on iPhone Neural Engine.

Usage:
    python scripts/train.py
    python scripts/train.py --epochs 200 --imgsz 1024
"""

import argparse
from pathlib import Path

from ultralytics import YOLO

DATA_YAML = Path(__file__).parent.parent / "data" / "dataset.yaml"
OUTPUT_DIR = Path(__file__).parent.parent / "models"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="yolov8n.pt", help="Base model (yolov8n/s/m)")
    parser.add_argument("--epochs", type=int, default=150, help="Training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    model = YOLO(args.model)

    results = model.train(
        data=str(DATA_YAML),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        patience=30,  # early stopping after 30 epochs without improvement
        project=str(OUTPUT_DIR),
        name="target_detector",
        exist_ok=True,
        # Augmentation — important with small dataset.
        hsv_h=0.015,
        hsv_s=0.4,
        hsv_v=0.4,
        degrees=15.0,      # rotation ±15° (targets aren't always straight)
        translate=0.1,
        scale=0.3,
        fliplr=0.0,        # NO horizontal flip (targets are oriented)
        flipud=0.0,        # NO vertical flip
        mosaic=0.5,
        mixup=0.1,
        perspective=0.001,  # slight perspective distortion
    )

    print(f"\nTraining complete. Best model: {OUTPUT_DIR}/target_detector/weights/best.pt")
    print(f"Run 'python scripts/export_coreml.py' to export for iOS.")


if __name__ == "__main__":
    main()
