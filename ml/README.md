# ML: Schießscheiben-Erkennung

YOLOv8-basierte Erkennung von Treffern auf Schießscheiben. Exportiert als Core ML-Modell für die iOS-App.

## Setup

```bash
cd ml
python3 -m venv .venv
source .venv/bin/activate
pip install ultralytics roboflow labelimg coremltools
```

## Daten vorbereiten

### Schritt 1: Fotos in `data/images/` kopieren

```bash
cp ~/Desktop/scheiben-fotos/*.jpg data/images/
```

### Schritt 2: Annotieren

**Option A: Roboflow (empfohlen, webbasiert)**
1. https://roboflow.com → neues Projekt "unefy-targets"
2. Upload alle Bilder
3. Klassen: `hit`, `patch`, `target_center`
4. Bounding Box um jeden Treffer, jedes Schusspflaster, und die Scheibenmitte
5. Export als "YOLOv8" Format → in `data/` entpacken

**Option B: labelImg (lokal)**
```bash
labelImg data/images/ data/labels/ data/classes.txt
```
Zeichne Bounding Boxes:
- `hit` — echter Einschuss (kleines Loch, ausgefranste Ränder)
- `patch` — Schusspflaster (großer runder Aufkleber)
- `target_center` — Scheibenmittelpunkt (für Kalibrierung)

### Annotation-Tipps
- **hit**: Bounding Box eng um das Loch, nicht den Hof/Riss
- **patch**: Box um den ganzen Aufkleber
- **target_center**: Kleine Box genau auf dem Zentrum der Scheibe
- Hintergrund-Löcher (außerhalb der Scheibe) NICHT annotieren
- Wenn Treffer und Pflaster überlappen → beide annotieren

### Schritt 3: Dataset aufteilen

```bash
python scripts/split_dataset.py
```

Erstellt `train/` (80%), `val/` (20%) Split.

## Training

```bash
python scripts/train.py
```

Dauert ~30 Min auf M1/M2 Mac, ~10 Min mit GPU.

## Export → Core ML

```bash
python scripts/export_coreml.py
```

Erzeugt `models/TargetDetector.mlpackage` → in die iOS-App kopieren.

## Klassen

| ID | Klasse | Beschreibung |
|---|---|---|
| 0 | `hit` | Echter Einschuss (Kugel-/Diabolo-Loch) |
| 1 | `patch` | Schusspflaster (Aufkleber zum Abdecken) |
| 2 | `target_center` | Scheibenmittelpunkt (Kalibrierungsanker) |
