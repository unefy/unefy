# ML: Schießscheiben-Erkennung

Treffer auf Schießscheiben finden — Scheibe lokalisieren, entzerren, Löcher
erkennen. Die Referenzimplementierung liegt hier in Python; die Apps portieren
sie (Kotlin/Swift) und werden gegen diese Skripte gegengeprüft.

**Die Geometrie braucht kein Modell**, die Treffererkennung womöglich doch.
Scheibe finden und entzerren ist gelöst: 142/142 lokalisiert, Fehler unter einem
Zehntel Ring. Löcher über lokalen Kontrast zu finden trägt auf elf von zwölf
handgeprüften Scheiben (97,5 % Präzision, 74 von 74 Löchern) — und scheitert auf
der zwölften an einer physikalischen Grenze, weil dort ein heller Kugelfang
durch die Löcher scheint. Beide Stände stehen unten, gemessen mit demselben
Maßstab. Details in [NOTES-real-targets.md](NOTES-real-targets.md) §8b.

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

## Die Strecke mit Modell

Der gemessene Fall ist da. Auf IMG_6717 findet der Regel-Detektor 3 von 9
Treffern, und der Grund ist strukturell: die Löcher auf dem Papier haben dort
Kernwerte von 33–40 bei einer Druckfarbe von 49 — sie sind **nicht dunkler als
der Druck**, weil ein heller Kugelfang durchscheint. Genau darauf beruht aber
die ganze Regel. Vier Auswege wurden durchgemessen (Schwelle auf Papier lockern,
Helligkeit unverwaschen prüfen, Suchbereich aufs Blatt ausdehnen, Kernschwelle
anheben) — jeder kostete mehr Präzision als er Treffer brachte, weil ein Loch
über hellem Kugelfang und eine gedruckte Ziffer denselben lokalen Kontrast
haben. Was sie trennt, ist Form und Textur.

**Die Geometrie bleibt klassisch.** Trainiert wird auf den entzerrten Crops, wo
ein Pixel 0,39 mm ist und die Scheibe immer gleich im Bild sitzt; das Modell
bekommt genau eine Aufgabe — Loch oder nicht.

```bash
# Crops + Vorab-Labels schreiben. Wo ein Foto in hits-truth.json steht, kommen
# die handgeprüften Löcher hinein, sonst die des Regel-Detektors.
python scripts/export_dataset.py --input ~/Documents/Scheiben

# ... Labels korrigieren (labelImg, Roboflow) ...

python scripts/split_dataset.py
python scripts/train.py
```

Gemessen wird das Modell mit **demselben** `score_hits.py` gegen dieselben
handgeprüften Löcher wie der Regel-Detektor. Alles andere wäre kein Vergleich.

## Daten vorbereiten

`export_dataset.py` oben schreibt Crops und Vorab-Labels; annotiert wird
ausschließlich darauf. Die frühere Strecke über die Rohfotos mit den Klassen
`hit`/`patch`/`target_center` ist entfallen — `target_center` löst die Geometrie
schon deterministisch, und `patch` kostete sechstausend Boxen für eine
Unterscheidung, die der Hintergrund dem Detektor ohnehin beibringt.

### Annotation-Tipps
- Box eng um Loch **plus ausgefransten Rand**, so wie die Vorab-Labels es tun
- Was der Regel-Detektor gesetzt hat, ist meistens richtig: **korrigieren, nicht
  neu zeichnen**. Fehlende Treffer ergänzen, Fehlmeldungen löschen.
- Pflaster **nicht** annotieren — sie sind Hintergrund
- Löcher im Kugelfang außerhalb des Blattes **nicht** annotieren
- Im Zweifel: bei 4-facher Vergrößerung nachsehen. Ein offenes Loch ist
  ausgefranst, ein gepflastertes eine glatte runde Scheibe (NOTES §8b)

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
| 0 | `hit` | Offenes Einschussloch auf dem Blatt |

Eine Klasse. Was kein Loch ist — Pflaster, Ringlinien, Ziffern, Kugelfang —
lernt der Detektor als Hintergrund.
