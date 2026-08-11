# Plan: Dokumentenablage

Stand 2026-08-12, Roadmap 6.6. Satzung, Protokolle, Formulare — Dateien, die
dem Verein gehören und die jemand hochlädt. Bisher gibt es im Code kein
einziges Byte Datei-Handling; das ist die eigentliche Nachricht dieses Plans.

## Abgrenzung, gleich am Anfang

**Bescheinigungen (6.3) werden erzeugt, hier werden Dateien abgelegt.** Das
sind zwei verschiedene Dinge, und sie werden sich im Kopf und im Code sofort
vermischen, wenn beide „Dokumente" heißen. Deshalb:

- Im Code heißt das hier **`library`** — `library_documents`, `/api/v1/library/…`,
  `components/library/…`. `documents` bleibt reserviert für Bescheinigungen.
- Im UI heißt es auf Deutsch **„Ablage"**, nicht „Dokumente".

**Nicht in diesem Plan:** Dateien *über ein Mitglied* (eingescannter Antrag,
Nachweis einer Ausbildung). Technisch fast dasselbe, rechtlich nicht: das sind
personenbezogene Daten mit eigener Aufbewahrungsfrist und eigenem
Löschanspruch. Die Ablage des Vereins zuerst, das Mitgliedsdokument danach und
bewusst — sonst landet ein Führungszeugnis im selben Regal wie die Satzung.

## Leitplanken

1. **Selbst gehostet ist der Normalfall.** Standard ist ein Volume auf der
   Platte, kein S3. `docker compose up` darf für eine hochgeladene Satzung
   keinen Objektspeicher voraussetzen. S3-kompatibel ist die *Option* für
   SaaS — dieselbe Codebasis, eine Einstellung.
2. **Kein Byte ohne Mandantenprüfung.** Es gibt keine öffentlichen Buckets und
   keine erratbaren URLs. Jeder Download läuft durch das Backend, das prüft,
   wer fragt. Auch bei S3 später: keine Presigned URLs in v1, weil sie die
   Autorisierung aus dem einen Weg herausnehmen, auf dem sie heute liegt.
3. **Der Dateiname ist Eingabe, kein Pfad.** Gespeichert wird unter
   `{tenant_id}/{uuid4}`, der Anzeigename steht in der Datenbank. Damit sind
   `../`, Doppelpunkte, Emoji und 300-Zeichen-Namen ein Anzeigeproblem und
   kein Sicherheitsproblem.
4. **Typprüfung an den Magic Bytes.** Eine Endung ist eine Behauptung. Was
   nicht mit den ersten Bytes zu seinem Typ passt, wird abgelehnt — dieselbe
   Prüfung wie bei der Unterschrift (`signature_png`), nur mit mehr Typen.
5. **Löschen muss löschen.** Eine Zeile auf `deleted_at` zu setzen und die
   Datei liegen zu lassen, ist bei einem Löschersuchen keine Löschung. Der
   Blob geht mit — beim Löschen, nicht irgendwann.
6. **Uploads gehen nicht durch eine Server Action.** Next begrenzt den Body
   einer Action auf 1 MB; ein Protokoll-Scan ist größer. Der Upload läuft über
   einen Route Handler, der zum Backend durchstreamt — dieselbe Bauform wie
   der PDF-Proxy, nur in die andere Richtung.

## Datenmodell

### `library_folders` (`TenantModel + AuditMixin`)

| Feld | Typ | Bemerkung |
|---|---|---|
| `parent_id` | UUID? → self, RESTRICT | NULL = Wurzel |
| `name` | String(255) | UniqueConstraint (tenant_id, parent_id, name) |
| `sort_order` | int | |

Ein Baum, kein flacher Katalog: „Protokolle ▸ 2026" ist genau das, was ein
Verein anlegt, sobald er das zweite Jahr abheftet. Verschieben prüft auf
Zyklen (ein Ordner darf nicht unter sich selbst wandern), Löschen nur, wenn
leer — ein Löschen, das ungefragt zwanzig Dateien mitnimmt, ist keins.

### `library_documents` (`TenantModel + AuditMixin + SoftDeleteMixin`)

| Feld | Typ | Bemerkung |
|---|---|---|
| `folder_id` | UUID? → library_folders, RESTRICT | NULL = Wurzel |
| `title` | String(255) | Anzeigename, änderbar |
| `description` | Text? | |
| `visibility` | String: `board` \| `members` | s. u. |
| `storage_key` | String(512) | `{tenant_id}/{uuid4}`, nie der Dateiname |
| `original_filename` | String(255) | nur zur Anzeige und für den Download |
| `content_type` | String(128) | *erkannt*, nicht das, was der Browser behauptet |
| `byte_size` | BigInteger | |
| `checksum_sha256` | String(64) | Integrität, Deduplizierung später |
| `uploaded_by_user_id` | UUID? | |
| `uploaded_at` | datetime | |
| `replaces_id` | UUID? → self | zeigt auf die abgelöste Fassung |
| `superseded_at` | datetime? | gesetzt, sobald eine neue Fassung existiert |

**Fassungen ohne zweite Tabelle.** Wer eine neue Satzung hochlädt, lädt sie
als neue Fassung derselben Ablage-Position hoch: neue Zeile, `replaces_id` auf
die alte, `superseded_at` an der alten. Die Liste zeigt standardmäßig nur
`superseded_at IS NULL`. Damit ist „welche Satzung galt 2024" beantwortbar,
ohne dass ein zweites Modell und ein zweiter Lesepfad entstehen.

**Sichtbarkeit: zwei Stufen, nicht fünf.**

- `board` — Vorstand und aufwärts (`owner`/`admin`/`board`).
- `members` — jedes angemeldete Mitglied des Vereins.

Öffentlich (ohne Anmeldung, für die Vereinswebseite) ist bewusst **nicht**
dabei: das ist ein anderes Produkt-Versprechen mit anderen Folgen (Indexierung,
Abmahnrisiko bei Fotos, Bandbreite) und gehört entschieden, nicht nebenbei
eingebaut. Sparten-Sichtbarkeit („nur die Jugend") ist entschieden gegen v1:
sie verdoppelt die Prüfung an jeder Lesestelle und in jedem Test, und ein
Verein kommt mit zwei Stufen erst einmal weit.

## Speicher

Ein schmales Protokoll, zwei Umsetzungen:

```python
class Storage(Protocol):
    async def put(self, key: str, stream: AsyncIterator[bytes],
                  *, max_bytes: int | None = None) -> StoredObject: ...
    def open(self, key: str) -> AsyncIterator[bytes]: ...
    async def delete(self, key: str) -> bool: ...
    async def exists(self, key: str) -> bool: ...
```

`put` gibt Größe und SHA-256 zurück, weil beide beim Durchlaufen ohnehin
entstehen — der Dienst müsste die Datei sonst ein zweites Mal lesen, um zwei
Spalten zu füllen. `max_bytes` bricht mitten im Strom ab: die Prüfung gegen
`Content-Length` ist eine Behauptung, diese hier ist die Grenze.

- **`LocalStorage`** — Standard. Schreibt unter `STORAGE_PATH/{key}`, mit
  `aiofiles` (ist bereits Abhängigkeit). Geschrieben wird in eine Temporärdatei
  und erst danach umbenannt, damit ein abgebrochener Upload keine halbe Datei
  hinterlässt, die aussieht wie eine ganze.
- **`S3Storage`** — später, kostet eine Abhängigkeit (`aioboto3`). Erst bauen,
  wenn eine Installation es braucht.

Damit gilt: **v1 kommt ohne eine einzige neue Python-Abhängigkeit aus.**
`python-multipart` steckt bereits in `fastapi[standard]`.

Neue Einstellungen in `app/config.py`:

| Einstellung | Standard | Zweck |
|---|---|---|
| `STORAGE_BACKEND` | `local` | `local` \| `s3` |
| `STORAGE_PATH` | `./var/storage` | nur `local` |
| `MAX_UPLOAD_BYTES` | 25 MB | pro Datei |
| `TENANT_STORAGE_QUOTA_BYTES` | 1 GB | pro Verein, geprüft beim Upload |

Das Kontingent ist kein SaaS-Detail, das man nachrüstet: ohne Obergrenze ist
ein Upload-Formular in einer Mehrmandanten-Installation eine offene Festplatte.

## API

Alles unter `/api/v1/library/…`, Schreiben nur `board` und aufwärts, Lesen
gefiltert nach `visibility`.

| Endpunkt | Rolle | Bemerkung |
|---|---|---|
| `POST /documents` (multipart) | board | Upload; validiert Typ, Größe, Kontingent |
| `POST /documents/{id}/version` | board | neue Fassung derselben Position |
| `GET /documents` | alle | Ordner, Suche, Paginierung; `board`-Dateien nur für den Vorstand |
| `GET /documents/{id}/content` | alle | streamt die Bytes |
| `PATCH /documents/{id}` | board | Titel, Beschreibung, Ordner, Sichtbarkeit |
| `DELETE /documents/{id}` | board | Zeile *und* Blob |
| `GET/POST/PATCH/DELETE /folders…` | board / alle (lesen) | Baum |

Antworten in der Hülle `{ data }`, Fehler mit den bestehenden Codes
(`NotFoundError` → 404, `ForbiddenError` → 403 statt 401, Konvention).

## Web

- Navigation: **„Ablage"** in der Gruppe *Vereinsleben*.
- Ordnerbaum links, Breadcrumb oben, Liste über die geteilte Data-Table
  (Sortier-Header und Filter, Konvention — keine handgerollte Tabelle).
- Upload per Klick und per Ziehen auf die Liste, mit Fortschritt. Große
  Dateien brauchen eine Anzeige, die sich bewegt, sonst drückt jemand zweimal.
- Download über einen Route Handler `app/api/library/[id]/content/route.ts`,
  gebaut wie der PDF-Proxy: Session-Cookie serverseitig weitergereicht, das
  Backend entscheidet, diese Route trägt nur Bytes.
- PDF und Bilder öffnen sich im Browser (`inline`), alles andere lädt herunter
  (`attachment`). Immer `X-Content-Type-Options: nosniff` und `Cache-Control:
  no-store`.
- i18n de+en von Anfang an.

## Sicherheit

- **Erlaubte Typen als Positivliste**, geprüft an den Magic Bytes: PDF, PNG,
  JPEG, WebP, ODF, OOXML (docx/xlsx/pptx), txt, csv, ics.
- **SVG bleibt draußen.** Ein SVG ist ausführbares Markup; im selben Ursprung
  ausgeliefert ist es ein Skript im Kontext der Anwendung.
- **Kein Virenscanner.** ClamAV wäre ein weiterer Dienst im Compose und läuft
  einer Vereins-Installation davon. Kompensation: Positivliste, nichts wird je
  ausgeführt, Auslieferung als Anhang mit `nosniff`. Das ist ehrlich
  aufzuschreiben, nicht zu verschweigen — wer Dateien austauscht, tauscht
  Risiko aus.
- **Prüfung im Backend, nicht im Browser.** Die Größenprüfung im Formular ist
  Höflichkeit, die im Endpunkt ist die Prüfung.
- **Protokolliert** werden Upload, Löschung und Änderung der Sichtbarkeit im
  `TenantAuditLog`. Downloads nicht: das wäre bei einem Formular, das jeder
  zieht, mehr Rauschen als Erkenntnis — und wenn eine Installation es doch
  braucht, ist es eine Einstellung, keine Umschreibung.

## Phasen

**Phase 0 — Speicher (kein UI). Fertig 2026-08-12.** `app/core/storage.py`
mit `Storage`-Protokoll und `LocalStorage`, die vier Einstellungen,
31 Tests gegen ein Temporärverzeichnis (`tests/test_storage.py`). Dazu das
Volume `storage_data` in `docker-compose.prod.yml` — ein `STORAGE_PATH` im
Container wäre eine Ablage, die sich beim nächsten `pull` selbst leert, und
das prüft jetzt ein Test mit. `STORAGE_BACKEND=s3` wird beim Start abgelehnt,
solange nichts dahintersteht. Keine neue Laufzeit-Abhängigkeit, nur
`types-aiofiles` für mypy.

**Phase 1 — Modell und API.** Migration, Modelle, Service mit Typ-, Größen-
und Kontingentprüfung, Endpunkte, Rollen. Ordnerbaum inklusive Verschieben mit
Zyklusprüfung und Fassungen über `replaces_id` — beide sind entschieden und
gehören damit in die Runde, in der das Modell entsteht.

**Phase 2 — Web.** Ordnerbaum, Liste, Upload, Download, Umbenennen,
Verschieben, Löschen. Ab hier ist es für einen Verein benutzbar.

**Phase 3 — Feinschliff.** Fassungshistorie im UI, Suche über Titel und
Beschreibung (nicht über den Inhalt — Textextraktion aus PDF ist ein eigenes
Thema), Mehrfachauswahl.

**Später, bewusst nicht jetzt:** S3, öffentliche Links, Mitgliedsdokumente,
Android-Spiegel (die Schreib-Queue kennt keine Binärdaten), Public API.

## Tests

Nach der Pyramide, ein pytest-Prozess gegen `unefy_test`. Tragend, also
jeweils rot gesehen:

- **Mandantentrennung**: Verein B bekommt die Datei von Verein A weder in der
  Liste noch über die direkte ID. Das ist der Test, der nicht fehlen darf.
- **Sichtbarkeit**: ein Mitglied sieht `board`-Dateien nicht — nicht in der
  Liste und nicht beim Abruf des Inhalts.
- **Typprüfung**: eine als PDF benannte ZIP-Datei wird abgelehnt.
- **Pfad**: ein Dateiname mit `../` landet trotzdem unter dem Schlüssel des
  Vereins.
- **Kontingent**: der Upload über die Grenze wird abgelehnt, und zwar bevor
  Bytes geschrieben werden.
- **Löschen**: nach `DELETE` ist der Blob im Speicher nicht mehr da.
- **Abbruch**: ein unterbrochener Upload hinterlässt keine sichtbare Datei.

## Entschieden (2026-08-12)

1. **Ordnerbaum ab v1.** So heftet ein Verein ab, und der Baum nachträglich
   einzuziehen hieße, jedes Listen- und UI-Stück ein zweites Mal zu bauen.
2. **Zwei Sichtbarkeitsstufen**, `board` und `members`. Sparten später, wenn
   ein Verein danach fragt.
3. **Fassungen über `replaces_id`.** Die Ablage verwaltet die Ordnung, nicht
   der Mensch mit Dateinamen.

## Noch offen

- **Kontingent und Größenlimit.** 1 GB je Verein und 25 MB je Datei sind
  gesetzt, aber geraten — ein eingescanntes Protokoll von zwölf Seiten liegt
  bei 3–8 MB. Beides ist eine Einstellung und lässt sich ohne Migration
  ändern, also blockiert es den Bau nicht.
