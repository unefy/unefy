# Beobachtungen an echten Scheibenfotos

Notizen aus der Sichtung von Realaufnahmen. Sie sind der Grund für mehrere
Entwurfsentscheidungen in Phase 2/3 und gehören gelesen, bevor jemand an der
Erkennungspipeline arbeitet.

Hauptaktivität des Vereins: **25 m Großkaliber-Pistole Präzision** — also die
Scheibe `sport_pistol_25m` mit 9 mm / .45, nicht die Luftdruckscheiben. Das ist
der Fall, der zuerst funktionieren muss.

## 1. Frische Treffer vs. Schusspflaster — das eigentliche Problem

Auf einer typischen Vereinsscheibe sitzen **deutlich mehr Pflaster als frische
Treffer** (gesichtet: ~40 Pflaster, ~8 frische Löcher). Aus einem Einzelbild ist
grundsätzlich nicht entscheidbar, welche Löcher zur aktuellen Serie gehören.

Was trägt: **ungepflastert = frisch.** Genau dafür wird nach jeder Serie
gepflastert, das ist gelebte Standpraxis. Konsequenzen:

- Das Modell braucht die Klasse `patch` nicht nur „auch", sie ist gleichwertig
  wichtig wie `hit` — die Mehrheit der runden Objekte auf der Scheibe sind
  Pflaster.
- Pflaster sehen je nach Zone unterschiedlich aus: außen hell/durchscheinend auf
  cremefarbenem Papier, im Spiegel schwarz auf schwarz. Beide Varianten müssen
  in den Trainingsdaten vorkommen, sonst versagt das Modell genau im Spiegel —
  dort, wo die Treffer zählen.
- Fällt die Heuristik aus (nicht gepflastert, mehrere Serien auf einem Blatt),
  bleibt nur ein Vorher-Foto und Differenzbildung. Als Ausbaustufe vorgesehen,
  nicht für V1.

## 1b. Eine Scheibe, zwei Schützen, zwei Kaliber

Gelebte Praxis: Mitglied A schießt KK, Mitglied B schießt 9 mm auf dasselbe
Blatt, danach wird abgeklebt. Ein Foto enthält also **zwei Serien von zwei
Mitgliedern**.

Datenseitig ist das bereits abgedeckt — zwei `Entry`-Zeilen in derselben
Session, jede mit ihrem eigenen Kaliber. Für die Erkennung folgt daraus:

- **Die Lochgröße ist das Trennmerkmal.** 5,6 mm gegen 9 mm ist Faktor 1,6 im
  Durchmesser und ~2,6 in der Fläche — im entzerrten Crop, wo der Maßstab
  bekannt ist, direkt messbar. Der Detektor soll deshalb den Lochdurchmesser
  mitliefern, nicht nur die Position.
- Daraus wird ein Bedienkonzept: Nutzer wählt Mitglied + Kaliber, die App
  schlägt die passenden Löcher vor. Danach dieselbe Scheibe, zweites Mitglied,
  zweites Kaliber, die verbleibenden Löcher.
- Das Modell braucht deshalb Trainingsbilder mit **gemischten Kalibern auf einem
  Blatt**, sonst lernt es die Größenachse nie.

Konsequenz auch für die manuelle Erfassung (Phase 1): Nach dem Speichern muss
„noch eine Serie auf derselben Scheibe" ein Klick sein — gleiche Session,
gleiche Disziplin, anderes Mitglied und Kaliber.

## 2. Die Scheibe hängt vor einer durchlöcherten Wand

Der Kugelfang (Schaumstoff/Gummi) ist selbst voller dunkler Einschusslöcher, und
im Bild liegen weitere dunkle Flächen (Wand, Schatten, Rahmen). Eine globale
Otsu-Schwelle findet mit hoher Wahrscheinlichkeit **nicht** den Spiegel.

→ Die geführte Aufnahme (Kreis-Overlay im Sucher, Suche nur innerhalb) ist
Pflicht, nicht Komfort.

## 3. Der Spiegel ist ein Annulus, kein Kreis

Der 10er ist hell ausgefüllt. Gemessen: heller Kern ≈ ¼ des Spiegeldurchmessers,
was bei 200 mm Spiegel genau den 50 mm des 10er-Rings entspricht.

- Die Konturverfolgung muss die **Außenkontur** der dunklen Region nehmen; auf
  die Innenkontur zu fitten liefert einen um Faktor 4 falschen Maßstab.
- Umgekehrt ist der helle Kern ein Geschenk: **zwei konzentrische Kreise mit
  bekanntem Durchmesser** bestimmen die volle Homographie samt Perspektivterm.
  Die im Plan als Ausbaustufe geführte Variante ist damit ohne Zusatzaufwand
  erreichbar.

## 4. Besserer erster Anker: das Blatt

Das cremefarbene Blatt hebt sich kräftig vom Hintergrund ab und ist ein
Rechteck. Vier Ecken ergeben eine echte 4-Punkt-Homographie — genauer als jede
Ellipsennäherung.

Vorgehen in dieser Reihenfolge:
1. Helles Viereck (Blatt) innerhalb des Overlays suchen → 4-Punkt-Homographie.
2. Darin den Spiegel als Ellipse fitten → Zentrum, Maßstab, Feinkorrektur.
3. Schlägt (1) fehl (Blatt beschnitten, gewellt, angenagelt), allein mit (2)
   weiterarbeiten.

Vorsicht: Das Blattformat variiert je nach Hersteller und Disziplin, der
Spiegeldurchmesser dagegen ist normiert. Der Maßstab kommt deshalb **immer aus
dem Spiegel**, nie aus dem Blatt; das Blatt liefert nur die Entzerrung.

## 5. Blatt ist größer als der Ringbereich

Ring 1 reicht nicht bis zum Blattrand. Das Canvas muss diesen Rand mitzeichnen,
sonst sieht die digitale Scheibe falsch aus. Ringzahlen stehen an vier
Positionen (oben, unten, links, rechts), außerhalb wie innerhalb des Spiegels.

**Nachgemessen im entzerrten Crop** (dort ist der Maßstab bekannt), sechs Fotos:
Blatt **~600 mm breit**, also 300 mm vom Zentrum zur Kante. Das Verhältnis
Blattkante zu Ring-1-Radius ist damit **1,2** — die frühere Schätzung 1,05…1,1
war zu klein. Bezogen auf den Spiegelradius: **3,0**. Diese Zahl ist der
Maßstab, an dem sich jede Blatterkennung messen lassen muss.

Praktische Folge: Treffer können **außerhalb von Ring 1** auf dem Blatt liegen —
auf der Scheibe des Schützen taten es drei von neun. Ein Detektor, der nur die
Ringfläche absucht, verliert sie.

## 5b. Den Blattrand findet man nicht über Helligkeit

Der grüne Rahmen im Sucher saß auf drei von vier echten Fotos falsch: die
Unterkante schnitt quer durch die Scheibe. Ursache ist keine Kleinigkeit im
Code, sondern das Verfahren — die Blattmaske entstand aus zwei globalen
Otsu-Schwellen, und die untere Blatthälfte liegt fast immer im Schatten. Sie
fällt damit auf die falsche Seite der Schwelle.

Gemessen über alle 142 Fotos, Maßstab ist das Verhältnis oben (Sollwert 3,00):

```
Helligkeitsschwelle   2,68   systematisch 11 % zu klein
Canny + Konturen      3,76   und nur 25 von 142 überhaupt gefunden
Strahlen vom Spiegel  3,02
```

Dokumentenscanner nehmen deshalb **Kanten** statt Helligkeit: ein Gradient hat
keinen Schattenverlauf. Ein Scanner muss das Blatt aber in einer unbekannten
Szene finden — wir kennen an dieser Stelle den Spiegel längst. Von ihm nach
außen zu tasten ist einfacher *und* genauer: entlang jedes Strahls ist Papier
hell, hinter der Kante dunkel, **und es bleibt dunkel**. Genau daran erkennt man
die Kante gegen einen Schatten, der wieder aufhellt.

Zwei Details, die es braucht:
- Ein einzelnes dunkles Pixel beendet den Strahl nicht (sonst endet er am ersten
  Loch oder Pflaster) — erst wenn der Median der nächsten zehn Pixel dunkel
  bleibt.
- Ausreißer-Strahlen werden verworfen, aber erst oberhalb von **1,41** des
  Medianradius: die Ecken eines Quadrats liegen legitim genau dort. Bei 1,25
  schneidet man sie ab und das Blatt kommt 8 % zu klein heraus.

## 6. Perspektive in der Praxis — gemessen

Erster Durchlauf über 142 reale Fotos (`~/Documents/Scheiben`, 2026-08-06):

```
142/142 Scheiben lokalisiert (100 %), 17 s gesamt
Rundheit (minor/major): schlechteste 0.96 · p10 0.97 · Median 0.99
unter 0.80: 0 von 142
```

**Konsequenz: Die volle Homographie wird nicht gebraucht.** Es wird faktisch
frontal fotografiert — die schlechteste Aufnahme im Bestand entspricht rund 16°
Neigung, wo die affine Ellipsen-Entzerrung noch deutlich innerhalb der
Ringbreite bleibt. Die im Plan als Ausbaustufe vorgesehene Zwei-Kreis-Homographie
ist damit vorerst gestrichen; die Warnschwelle `b/a < 0.8` bleibt als Netz für
Ausreißer im Feld.

Nachprüfen lohnt sich, sobald Fotos von anderen Ständen oder Mitgliedern
dazukommen — Handhaltung ist Gewohnheit, und dieser Bestand stammt von einer
Quelle.

Wie genau die Entzerrung dabei ist, sagt `measure_accuracy.py` über die
gedruckten Ringlinien — 568 Messungen aus denselben 142 Fotos:

```
Crop 1600:  Median +2,2 mm   Streuung 6,3 mm   (9 % eines 25-mm-Rings)
Crop  640:  Median +1,6 mm   Streuung 7,1 mm   (6 %)
```

Der Fit ist in beiden Fällen derselbe; der Unterschied steckt im Messverfahren
(dunkelstes Pixel in einem ±12,5-mm-Fenster) und liegt unter dessen eigener
Streuung. Beides heißt dasselbe: der Fehler der ganzen Kette bleibt deutlich
unter einem Zehntel Ring.

## 7. Zwei Fallen, die erst echte Fotos aufgedeckt haben

Beide kosteten je ~20 % des Bestands, beide meldeten sich **nicht** als Fehler,
sondern als plausibel aussehendes Unsinn-Ergebnis:

1. **Der Kugelfang landet in der Blattmaske.** Ein einzelner Otsu-Durchgang
   trennt „Scheibe + Kugelfang" von „dunkler Rest" — der graue Schaumstoff liegt
   also mit auf der hellen Seite. Da er dunkler ist als das Papier, wird er
   innerhalb der Maske zur größten dunklen Region, und die Ellipse legt sich um
   den *Kugelfang* statt um den Spiegel. Behoben durch einen zweiten
   Otsu-Durchgang nur über die helle Seite.
2. **Es fehlte jede Größenschranke.** Der Fit akzeptierte einen „Spiegel", der
   1,56-mal so breit war wie das ganze Blatt. Jetzt muss die Marke zwischen 8 %
   und 65 % der Blattbreite liegen.

Lehre für den Kotlin-Port: Eine Erkennung, die „etwas gefunden" meldet, ist
wertlos ohne Plausibilitätsprüfung. Die Nachkontrolle — entzerren, erneut
fitten, Radius und Rundheit gegen den Erwartungswert halten — gehört mit
portiert.

## 8. Treffer gegen Pflaster — der Blick bei voller Auflösung

Bei 1600 px Cropgröße ist der Unterschied im Bild eindeutig (Ausschnitt aus dem
Spiegel von IMG_1560):

- **Frischer Treffer**: tiefschwarz, ausgefranster Rand. Ein Loch wirft Schatten,
  es ist dunkler als *alles* andere auf der Scheibe.
- **Pflaster**: gleichmäßig grau, kreisrund, glatte Kante — und im Spiegel
  **heller** als der Untergrund.

Erste Messung: eine absolute Helligkeitsschwelle trennt sie **nicht**, weil der
Spiegel selbst bei 45–70 liegt und damit im selben Bereich wie ein Loch auf
Papier. Was trägt, ist **lokaler Kontrast**: Innenhelligkeit des Blobs gegen
seinen Ring von Nachbarpixeln. Ein Loch ist deutlich dunkler als seine Umgebung,
ein Pflaster im Spiegel heller, ein Pflaster auf Papier nur leicht dunkler.

**Das eröffnet die Möglichkeit, Phase 3 ohne Modell zu beginnen.** Erst messen,
wie weit klassische Bildverarbeitung trägt; ein Detektor ist dann nur noch für
die Fälle nötig, die sie nicht sicher trennt (überlappende Löcher, Treffer genau
auf einer Ringlinie).

### 8b. Gemessen: sie trägt weit genug

`scripts/detect_hits.py` setzt genau das um, `scripts/score_hits.py` misst es
gegen 74 von Hand geprüfte Löcher in elf Fotos (`data/hits-truth.json`):

```
Präzision 97,4 %  (2 gemeldete Löcher waren keins, beide im am dichtesten
                   zerschossenen Bild)
Recall   100,0 %  (kein geprüftes Loch blieb unentdeckt)
```

Ein Modell wird für die 25-m-Scheibe damit vorerst **nicht** gebraucht. Die
Klasse `patch` fällt gleich mit weg: ein Pflaster muss nie erkannt werden, es
scheitert von selbst an der Bedingung unten.

Was die Trennung wirklich leistet, ist nicht der lokale Kontrast allein, sondern
er zusammen mit einer physikalischen Tatsache:

> **Ein Loch ist dunkler als die eigene Druckfarbe der Scheibe.**

Spiegel und Ringzahlen sind dieselbe Farbe; ein Loch ist ein Schatten in den
Kugelfang dahinter. Beide Bezugswerte — Druckfarbe und Papier — werden aus dem
Bild selbst gelesen (Median über zwei große Ringflächen), also sind alle
Schwellen Verhältnisse und keine Helligkeiten. Belichtung kürzt sich weg, ein
angehobener Schwarzwert (Dunst, Streulicht) allerdings nicht.

Zahlen aus IMG_1560: Loch 5–9, Druckfarbe 56–68, Papier 205, Pflaster 190 auf
Papier und 56–67 im Spiegel.

Drei Dinge, die erst die echten Fotos gezeigt haben:

1. **Auf Papier sind Löcher grau, nicht schwarz** (0,38–0,40 der Druckfarbe statt
   0,1), weil durch sie der helle Kugelfang zu sehen ist statt Schatten. Die
   Schwelle muss deshalb davon abhängen, worauf das Loch sitzt: im Spiegel
   konkurriert sie mit der dunklen Naht zwischen zwei Pflastern und muss streng
   sein, auf Papier gibt es unterhalb der Druckfarbe überhaupt keine
   Konkurrenz.
2. **Der gemessene schwarze Kern ist kleiner als das Kaliber** — 7,2 mm bei 9 mm,
   3,1 mm bei vermutlich .22. Für die Kaliber-Trennung (§1b) reicht das, weil
   der Fehler auf einem Blatt derselbe ist; als Millimeterwert taugt er nicht.
3. **Was aussieht wie ein frisches Loch, ist oft ein gepflastertes.** Auf
   IMG_1528 waren fünf „offensichtliche Treffer" beim Blick mit 6-fachem Zoom
   verbeultes Papier über alten Löchern — der Detektor lag richtig und das Auge
   falsch. Genau dafür ist der Kontaktbogen aus Einzelkacheln da, mit dem
   `hits-truth.json` entstanden ist.

### 8b2. Was der Kotlin-Port erzwungen hat

Die App führt dieselbe Erkennung ohne OpenCV aus. Drei Stellen, an denen die
Python-Fassung etwas benutzt hat, das drüben nicht existiert — alle drei wurden
in **Python** geändert, damit beide Seiten dieselbe Größe berechnen:

1. **Fläche**: `cv2.contourArea` legt das Polygon durch die Pixel*mitten* und
   verliert damit den halben Rand — bei einem 19-Pixel-Blob misst es 12. Jetzt
   zählen beide Seiten Pixel. Danach musste `MIN_HOLE_MM` von 1,6 auf 2,0, weil
   dieselben Blobs plötzlich größer messen; Präzision und Recall blieben gleich.
2. **Strukturelement**: der Hintergrund wurde mit einer Kreisscheibe geschlossen.
   Ein Quadrat ist separabel und damit in vier linearen Durchläufen statt einem
   quadratischen zu haben — bei 50 px Kernel der Unterschied zwischen
   Millisekunden und Minuten. Gemessen gegen die geprüften Löcher: identisch.
3. **Umfang**: `arcLength` läuft über die Kettencodierung der Kontur. Kotlin
   verfolgt den Rand jetzt selbst (Moore-Nachbarschaft, Diagonale als √2) und
   kommt auf dieselbe Zahl.

Dazu ein Fehler, der nur im Port sichtbar wurde und für jeden JVM-Test mit
Graustufenbildern gilt: **`BufferedImage.getRGB()` rechnet bei einem
Graustufenbild von linearem Grau nach sRGB um.** Ein Loch mit Wert 68 kommt als
141 an, und alle Schwellen sitzen woanders. Direkt aus dem Raster lesen
(`raster.getSample`).

### 8c. Die Entzerrung dreht nicht mit

Aufgefallen bei den synthetischen Tests, gilt aber für jedes Foto: `rectify.py`
macht aus der Ellipse wieder einen Kreis, nimmt aber **die Kameradrehung nicht
heraus**. Der Crop — und damit jede gemeldete Trefferkoordinate — ist um die
Handhaltung gedreht.

- Für die **Ringzahl** ist das folgenlos, die ist ein Radius.
- Für ein **gezeichnetes Scheibenbild** ist es sichtbar: das ganze Trefferbild
  steht schief.

Zu beheben wäre es in `rectify.py` über die Blattkanten (`minAreaRect` auf der
Blattmaske, Winkel modulo 90°; die Vierfachsymmetrie des Drucks macht die
90°-Mehrdeutigkeit harmlos). Bis dahin heißt „x_mm/y_mm" eben: im gedrehten
Rahmen des Fotos.

## 9. Cropgröße bestimmt, was überhaupt erkennbar ist

| Crop | mm/px | 9 mm Loch | 4,5 mm Diabolo |
|------|-------|-----------|----------------|
| 640  | 0,90  | 10 px     | 5 px           |
| 1280 | 0,45  | 20 px     | 10 px          |
| 1600 | 0,36  | 25 px     | 13 px          |

640 war zu klein — für einen Detektor wie für einen Menschen, der einen Treffer
genau setzen will. Die App entzerrt jetzt auf 1600 über einen 1,25-fachen
Rahmen, also 2,56 px/mm. Für Luftdruck (4,5 mm) wäre
selbst das knapp; falls die Erkennung dort gebraucht wird, muss der Crop mit dem
Scheibentyp skalieren statt fest zu sein.

Die Cropgröße selbst wurde gemessen, nicht geschätzt: gegen `hits-truth.json`
gewinnt 1600 gegen 1280 (mehr Löcher) **und** gegen 1800/2000 — feiner löst
Papierkorn und JPEG-Rauschen in Blobs von Lochgröße auf und kostet Präzision.

Nachtrag aus den Detektor-Tests: begrenzend ist bei Luftdruck nicht die
Cropgröße, sondern die **Auflösung des Fotos**. Bei 2 px/mm auf dem Blatt verschwindet der schwarze Kern
eines 4,5-mm-Lochs unter 2 mm und kein Crop holt ihn zurück; ab etwa 3,4 px/mm
werden alle gefunden. Für Luftdruck heißt das: Blatt formatfüllend aufnehmen.
Der Crop muss außerdem aus dem **Originalfoto** gewarpt werden, nicht aus der
1024-px-Arbeitskopie, sonst sind die zusätzlichen Pixel Interpolation.
