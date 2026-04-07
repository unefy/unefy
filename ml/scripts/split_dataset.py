"""Split annotated images into train/val sets (80/20).

Expected input layout:
  data/images/  ← all .jpg/.png files
  data/labels/  ← matching .txt YOLO annotation files

Output layout:
  data/train/images/ + data/train/labels/
  data/val/images/   + data/val/labels/
"""

import random
import shutil
from pathlib import Path

SEED = 42
SPLIT_RATIO = 0.8

data_dir = Path(__file__).parent.parent / "data"
images_dir = data_dir / "images"
labels_dir = data_dir / "labels"

# Collect all annotated images (must have a matching .txt label file).
image_files = sorted([
    f for f in images_dir.iterdir()
    if f.suffix.lower() in {".jpg", ".jpeg", ".png"}
    and (labels_dir / f.with_suffix(".txt").name).exists()
])

if not image_files:
    print(f"No annotated images found in {images_dir}")
    print(f"Make sure labels exist in {labels_dir}")
    raise SystemExit(1)

random.seed(SEED)
random.shuffle(image_files)

split_idx = int(len(image_files) * SPLIT_RATIO)
train_files = image_files[:split_idx]
val_files = image_files[split_idx:]

for split_name, files in [("train", train_files), ("val", val_files)]:
    split_images = data_dir / split_name / "images"
    split_labels = data_dir / split_name / "labels"
    split_images.mkdir(parents=True, exist_ok=True)
    split_labels.mkdir(parents=True, exist_ok=True)

    for img_path in files:
        label_path = labels_dir / img_path.with_suffix(".txt").name
        shutil.copy2(img_path, split_images / img_path.name)
        shutil.copy2(label_path, split_labels / label_path.name)

print(f"Split complete: {len(train_files)} train, {len(val_files)} val")
