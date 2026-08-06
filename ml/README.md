# ML: Schießscheiben-Erkennung

Treffer auf Schießscheiben finden — Scheibe lokalisieren, entzerren, Löcher
erkennen. Die Referenzimplementierung liegt hier in Python; die Apps portieren
sie (Kotlin/Swift) und werden gegen diese Skripte gegengeprüft.

**Für die 25-m-Scheibe wird dafür kein Modell gebraucht.** Klassische
Bildverarbeitung über lokalen Kontrast erreicht auf handgeprüften Fotos 97,4 %
Präzision bei 100 % Recall — Details und Messmethode in
[NOTES-real-targets.md](NOTES-real-targets.md) §8b. Die YOLO-Strecke weiter
unten bleibt für die Fälle stehen, die sie nicht sicher trennt.

## Setup

```bash
cd ml
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Die Pipeline ohne Modell

```bash
# 1. Scheibe finden und entzerren — schreibt quadratische Crops, in denen
#    ein Pixel eine bekannte Zahl Millimeter ist
python scripts/rectify.py --input ~/Documents/Scheiben --out data/rectified --report

# 2. Wie genau die Entzerrung war, gemessen an den gedruckten Ringlinien
python scripts/measure_accuracy.py --input data/rectified

# 3. Löcher finden. --overlay schreibt Bilder mit eingekringelten Treffern,
#    --report fasst zusammen, --tones zeigt die Verteilung hinter der Schwelle
python scripts/detect_hits.py --input ~/Documents/Scheiben --overlay out/ --report

# 4. Gegen die von Hand geprüften Löcher in data/hits-truth.json messen.
#    Nach JEDER Änderung am Detektor, vor jedem Glauben daran.
python scripts/score_hits.py --input ~/Documents/Scheiben --per-image

# 5. Fixtures für die Android-Tests neu schreiben — nur nötig, wenn sich die
#    gemeldeten Positionen ändern. Der Diff ist die Regressionskontrolle.
python scripts/export_fixtures.py
```

Die Android-App trägt dieselbe Pipeline in Kotlin (`TargetLocator`,
`HitDetector`), weil OpenCV auf dem Telefon 30 MB und ein
16-KB-Alignment-Problem kostet. Beide Seiten werden gegen dieselben echten Fotos
gemessen: `HitDetectorTest` lässt die Kotlin-Fassung über die von
`export_fixtures.py` geschriebenen Crops laufen und vergleicht mit dem, was hier
herauskommt. Wer eine Schwelle hier ändert, ändert sie dort mit.

Beide Stufen haben synthetische Tests, die ohne echte Fotos laufen und sagen,
wie weit daneben es liegt statt nur ob etwas gefunden wurde:

```bash
python scripts/test_rectify.py
python scripts/test_detect_hits.py
```

## Die Strecke mit Modell (offen)

Erst anfangen, wenn ein gemessener Fall zeigt, dass die Pipeline oben ihn nicht
löst — überlappende Löcher näher als ein halber Durchmesser, Treffer genau auf
einer Ringlinie, ein Scheibentyp mit anderem Druckbild. `score_hits.py` sagt,
welche das sind.

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
