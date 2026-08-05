# Plan: Termin ↔ Einheit ↔ Nachweis

Ziel: Die drei Ebenen sauber trennen und verbinden, statt die Anwesenheit als
Anhängsel des Scanners zu behandeln.

| Ebene | Was sie ist | Träger |
|---|---|---|
| **Termin** (`Event`) | Ankündigung + Anmeldung vorab (RSVP, Warteliste) | Kalender |
| **Einheit** (`AttendanceSession`) | vom Verein betriebener Rahmen mit Aufsicht, geöffnet/geschlossen, attestiert | Verein |
| **Nachweis-Eintrag** (`AttendanceRecord`) | ein Schießtag einer Person, mit Herkunft und Beweisgüte | Person |

Leitsatz (mit Nutzer abgestimmt, 2026-08-05): **Der Nachweis hängt nicht am
Termin — er hängt an der Person und hat eine Herkunft.** Der Termin ist ein
optionaler Auslöser für eine Einheit, mehr nicht. Zwei Fälle sprengen jede
Pflicht-Verknüpfung:

1. Ad-hoc: Die Aufsicht steht am Stand, es existiert kein Termin, sie startet
   die Einheit aus dem Scanner. Dieser Weg bleibt.
2. Selbst geführt: Ein Mitglied geht allein auf einen (fremden) Stand und will
   seinen §14-Nachweis selbst führen. Es gibt weder Termin noch Einheit noch
   Aufsicht — heute gar nicht abbildbar, weil `session_id` Pflicht ist.

Zweites Motiv: **Erreichbarkeit.** Die Anwesenheitsliste (eigener Screen seit
2026-08-05, hinter dem Scanner) ist zu versteckt. Über den Termin verknüpft
bekommt sie einen natürlichen zweiten Eingang: wer den Übungsabend im Kalender
öffnet, sieht dort, wer da war.

## Ist-Zustand (verifiziert 2026-08-05)

- `backend/app/models/attendance.py:74`: `AttendanceSession.event_id` (FK
  `events.id`, SET NULL, nullable) **existiert, ist aber tot** — kein Service
  validiert es, kein Endpoint befüllt es, keine UI zeigt es. Bewusste
  Entscheidung von damals: docs/plans/attendance-and-shooting-proof.md, „Bewusst
  nicht direkt an `Event` gehängt".
- `AttendanceRecord.session_id` ist NOT NULL; `method = "self"` bedeutet heute
  ausschließlich den Selbst-Check-in der Aufsicht **innerhalb** einer
  Vereinseinheit (`assurance = "low"`, serverseitig abgeleitet).
- Die Bescheinigung (`ShootingProofCertificate`) weist bereits
  `self_certified_days` und `corroborated_self_days` aus, beide im
  `content_hash`. Ausgestellte Bescheinigungen: prüfen — nach der ersten echten
  Ausstellung braucht jede Felderweiterung eine Payload-Versionierung.
- `EventRegistration` (RSVP) und `AttendanceRecord` (Anwesenheitsbeleg) sind
  vollständig getrennt; kein Endpoint verbindet Termin und Einheit.
- Web: `apps/web/app/(app)/` hat `attendance`, `members`, `settings`,
  `shooting` — **keine Termine-UI**. Android: Termine-Feature vorhanden
  (`feature:events`), Scanner + Anwesenheitsliste in `feature:attendance`
  (Listen-Screen `AttendanceListKey(sessionId, sessionTitle)`).
- Retention: `app/tasks/retention.py` löscht `attendance_records` hart nach
  `tenants.attendance_retention_years` — gilt automatisch auch für alles, was
  dieser Plan in dieselbe Tabelle legt.
- Letzte Alembic-Revision: `34bbb220afd3` (member gender + federation).

## Strang A: Termin ↔ Einheit

### A1. Backend: `event_id` zum Leben erwecken

- `AttendanceService.create_session`/`update_session`: gesetztes `event_id`
  tenant-scoped laden, sonst 422. Kein Auto-Verhalten darüber hinaus.
- Session-Responses: `event_id` + `event_title` per Join mitliefern (Muster:
  `member_name` in `repositories/due.py::get_all_with_member`).
- Eindeutigkeit weich halten: mehrere Einheiten pro Termin bleiben erlaubt
  (zwei Stände am selben Abend). Kein Unique-Constraint.

### A2. Backend: Einheit aus Termin

- `POST /api/v1/events/{event_id}/attendance-session` (require_board):
  erzeugt eine offene Einheit mit Titel/Ort/Zeiten aus dem Termin
  (`opens_at = starts_at`, `closes_at = ends_at`, Fallback wie im Scanner
  8 h), `event_id` gesetzt. Existiert schon eine **offene** Einheit zum
  Termin, wird die zurückgegeben statt eine zweite zu erzeugen (idempotent
  fürs Doppel-Tippen; eine zweite lässt sich weiterhin bewusst über
  `POST /attendance/sessions` anlegen).
- `GET /api/v1/events/{event_id}` (bzw. Listen-Response): verknüpfte
  Einheit(en) mit Status + `record_count` mitliefern, damit Clients den
  Einstieg rendern können, ohne die Attendance-API abzugrasen.

### A3. App (Android): der zweite Eingang

Das ist der Kern des Erreichbarkeits-Problems:

- **Termin-Detail** (`feature:events`): Wenn eine Einheit verknüpft ist, eine
  Zeile „Anwesenheit (12)" → öffnet `AttendanceListKey(sessionId, titel)`.
  Modulregel beachten: Features reden nicht miteinander — der Klick reicht
  einen Nav-Key durch `app/` (wie `onOpenScanner` heute), die Liste selbst
  bleibt in `feature:attendance`.
- Für `board`+ zusätzlich: kein verknüpfter offener Termin heute → Aktion
  „Einheit starten" (ruft A2); danach direkt in den Scanner.
- **Scanner**: Beim Einheit-Anlegen aus dem Scanner die heutigen Termine
  anbieten (Titel vorbefüllt, `event_id` gesetzt); „ohne Termin starten"
  bleibt der erste Knopf. Kein Zwang, keine Phantom-Termine.
- Sichtbar machen, nicht nur verlinken: Session-Chips im Scanner zeigen den
  Termin-Titel, wenn einer verknüpft ist.

### A4. Später (nicht in diesem Plan umsetzen)

- RSVP gegen Anwesenheit spiegeln: „angemeldet und nicht gekommen" /
  „gekommen ohne Anmeldung" am Termin. Reine Leseansicht, kein neues Modell.
- Web-Termine-UI existiert nicht; sobald sie kommt, denselben Einstieg bauen.

## Strang B: Selbst geführte Nachweise (fremder Stand)

### B1. Modell: gleiche Tabelle, neue Herkunft

`attendance_records` bleibt das eine Nachweis-Hauptbuch — die §14-Auswertung
zählt `occurred_on`-Tage, die Schießdetails (`ShootingRecordDetail`) hängen am
Record, die Retention greift automatisch. Eine Zweittabelle würde all das
duplizieren.

- `session_id` → nullable.
- Neu: `origin: String(20)`, NOT NULL, Default `"club"`; Werte `"club"` |
  `"external"`.
- Neu: `external_location: String(255)`, nullable — Name des fremden Stands.
- CHECKs: `origin = 'external'` ⇒ `session_id IS NULL`, `member_id IS NOT
  NULL` (kein Gast führt fremde Nachweise), `external_location IS NOT NULL`.
  Umgekehrt: `origin = 'club'` ⇒ `session_id IS NOT NULL`.
- `method = "self"`, `assurance = "low"` — serverseitig gesetzt, wie beim
  Selbst-Check-in. Der Client kann keine Herkunft und keine Güte behaupten.
- Migration: `down_revision = "34bbb220afd3"`, handgeschrieben im Stil der
  bestehenden.

Nicht anfassen: die Close-Hash-Kette. Sie bezeugt Einheiten; externe Einträge
stehen in keiner Kette und behaupten das auch nicht — ihre Güte ist `low`, und
genau das ist die ehrliche Aussage.

### B2. Endpoints (Mitglieder-Selbstservice)

Unter `/api/v1/attendance/me`, neben `me/seed` und `me/records`:

- `POST /me/entries` — Datum, `external_location`, optional Notiz. Erzeugt den
  Record (`origin = external`). Datum nicht in der Zukunft; älter als N Tage
  (Vorschlag: 30) → 422, ein Nachweis wird zeitnah geführt.
- `GET /me/entries` — die eigenen externen Einträge.
- `DELETE /me/entries/{id}` — Soft-Delete nur eigener externer Einträge,
  solange keine Bescheinigung sie referenziert (`record_ids` der Zertifikate).
- Schießdetails: `PATCH /modules/shooting/records/{id}` erlaubt zusätzlich zum
  Vorstand auch das Mitglied selbst, **wenn** der Record ein eigener
  `external`-Eintrag ist. So funktionieren Disziplin/Waffe/Schüsse unverändert
  über das vorhandene Modul.
- Kein Modul-Gate auf den `me/entries`-Endpoints selbst (Anwesenheit ist
  generisch), aber die App zeigt den Einstieg nur Vereinen mit
  Schießsport-Modul — außerhalb davon gibt es keinen Grund, fremde Stände zu
  dokumentieren.

### B3. Auswertung und Bescheinigung

- Tageszählung: `occurred_on` zählt wie bisher; ein externer Eintrag am selben
  Tag wie ein Vereinsbesuch erzeugt keinen Doppeltag (Tagesgranularität
  dedupliziert von selbst).
- `self_certified_days` erfasst bereits „Tage, die nur auf dem eigenen Wort
  ruhen" — externe Einträge fallen genau darunter, ohne Formeländerung.
  **Aber:** die Korroborations-Prüfung ist tagesbasiert; ein externer Eintrag
  darf nicht dadurch „bestätigt" wirken, dass dieselbe Person am selben Tag
  auch im Verein war. Prüfen und ggf. auf Record-Ebene (`origin`) schärfen.
- Bescheinigung weist zusätzlich `external_days` aus (im `content_hash`, siehe
  Formatwarnung im Ist-Zustand). Ob und wie viele externe Tage ein Verband
  anerkennt, ist Sache der Regeltabelle (`ShootingProofRule`, z. B. künftig
  `max_external_days`), nicht des Codes.

### B4. App-UI

- Einstieg im Check-in-Bereich („Mein Check-in"): unter dem eigenen Code eine
  Zeile „Meine Schießtage" → Liste eigener Einträge (Verein + extern,
  gekennzeichnet), FAB/Aktion „Eintrag erfassen" (Datum, Stand, Disziplin/
  Waffe/Schüsse in einem Formular; Details via B2-PATCH).
- Kennzeichnung ehrlich halten: externe Einträge tragen sichtbar „selbst
  geführt" — dieselbe Sprache wie „Selbst eingetragen" im Scanner.
- Später: Beleg-Foto (gestempelter Standbucheintrag) als Anhang. Braucht
  Datei-Upload-Infrastruktur, bewusst nicht in diesem Plan.

## Reihenfolge & Tests

1. **A1 + A2** (Backend, eine Migration ist hier nicht nötig — `event_id`
   existiert): Validierung, Joins, Event-Endpoint. Tests in `test_events.py` /
   `test_attendance.py`: fremder Tenant → 404, unauthentifiziert → **403**
   (Konvention), Idempotenz von A2, `event_title` im Response.
2. **B1 + B2** (Backend, eine Migration): CHECKs testen (external ohne
   location → 422, Gast-extern → DB-Fehler abgefangen), Datum-Fenster,
   Details-PATCH-Berechtigung (Mitglied nur eigene externe), Zertifikat-Sperre
   beim Löschen.
3. **B3**: Auswertungs-Tests — externer Tag zählt, dedupliziert, erscheint in
   `self_certified_days` + `external_days`, Korroborations-Kante.
4. **A3 + B4** (Android): Termin-Detail-Einstieg, Scanner-Vorbefüllung, Meine
   Schießtage. Nav-Keys über `app/`, `EntryProviderCoverageTest` deckt neue
   Keys automatisch.
5. Web zieht nach, sobald es eine Termine-UI gibt (A4).

Backend-Tests: ein pytest-Prozess, geteilte `unefy_test`-DB (parallele Läufe
erzeugen Phantom-Fehler).

## Offene Fragen

- Anerkennungsregeln für externe Tage (Verbandssache): nur Ausweis oder auch
  Deckelung via Regeltabelle?
- Soll die eingetragene Standaufsicht die einzige sein, die scannen darf?
  (Alt, unverändert offen — siehe attendance-and-shooting-proof.md.)
- Rückwirkende Erfassungsfrist für externe Einträge: 30 Tage richtig?
- Beleg-Foto: Speicherort/Retention, wenn Upload-Infrastruktur kommt.
