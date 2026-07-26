# Plan: Event ↔ Competition Verknüpfung

Ziel: Events sind die Kalender-/Anmeldeebene, Competitions (Liga/Wettkampf/Trainingsserien
mit Sessions/Entries, genutzt von der iOS-App) die Sport-/Ergebnisebene. Eine
Competition-Session soll optional als Event im Kalender erscheinen — Anmeldung läuft über
das Event, Ergebnisse über die Session.

Faustregel (mit Nutzer abgestimmt): Ergebnisse erfassen → Competition. Nur Termin +
Teilnahme → Event. `event_type: "competition"` wird primär über den Link gesetzt.

## Ist-Zustand (verifiziert 2026-07-26, alle Checks grün)

- `backend/app/models/event.py`: `Event` (title, event_type, starts_at/ends_at tz-aware,
  all_day, registration_required, registration_deadline, max_participants, status) und
  `EventRegistration` (Warteliste + Nachrücklogik in `app/services/event.py`).
- `backend/app/models/competition.py`: `Competition` → `Session` (name, `date` (Date!),
  location, discipline) → `Entry`. API in `app/api/v1/competitions.py`
  (Sessions: POST/GET/DELETE unter `/{competition_id}/sessions`, kein PATCH).
- Web: `/events`-Seite vorhanden (`apps/web/components/events/*`), **keine** Competition-UI
  im Web (Competitions = Backend + iOS).
- Letzte Alembic-Revision: `e5a3c8d94f12`.

## Schritte

### 1. Backend: Schema + Migration

- `Event` erweitern: `competition_id: UUID | None` (FK `competitions.id`, ondelete SET NULL)
  und `session_id: UUID | None` (FK `sessions.id`, ondelete SET NULL), beide indexiert
  (`ix_events_tenant_session` auf tenant_id+session_id).
- Alembic-Migration, `down_revision = "e5a3c8d94f12"`. Handgeschrieben im Stil der
  bestehenden (alembic/versions ist von ruff excluded).

### 2. Backend: Schemas + API

- `schemas/event.py`: `competition_id`/`session_id` in Create/Update/Response
  (+ optional `competition_name` im Response für die UI).
- `services/event.py` create/update: wenn `session_id` gesetzt → Session laden
  (tenant-scoped!), validieren dass sie zur `competition_id` gehört (sonst 422);
  `event_type` automatisch auf `"competition"` setzen, wenn Link vorhanden.
- Event-Liste/-Detail: `competition_name` per Join mitliefern (Muster: `member_name`
  in `repositories/due.py::get_all_with_member`).

### 3. Backend: Session → Kalender-Event

- `POST /api/v1/competitions/{competition_id}/sessions` bekommt optionales Flag
  `create_calendar_event: bool` (Default false) + optionale `starts_at`-Zeit:
  erzeugt ein Event (title = Session-Name oder Competition-Name, starts_at aus
  Session-`date`, location übernommen, `session_id`/`competition_id` gesetzt).
- `DELETE .../sessions/{session_id}`: verknüpftes Event soft-deleten.
- In `_session_response` die `event_id` mitliefern (Query auf events by session_id).

### 4. Tests (tests/test_events.py erweitern + test_competitions.py)

- Event mit gültigem/ungültigem Session-Link (422 bei Session aus fremder Competition,
  404 bei fremdem Tenant — Konvention: unauthentifiziert = **403**, nicht 401).
- Session mit `create_calendar_event=true` → Event existiert, Felder übernommen.
- Session löschen → Event soft-deleted.
- `event_type` wird bei Link automatisch "competition".

### 5. Web-UI

- `lib/types/event.ts` + `hooks/use-events.ts`: neue Felder.
- Event-Panel (`components/events/event-panel.tsx`): Competition-Name als Badge/Link
  anzeigen, wenn verknüpft.
- Event-Create-Dialog: optionales Select "Mit Wettkampf verknüpfen" (Competitions via
  neuem `hooks/use-competitions.ts`, GET `/api/v1/competitions`), darunter Session-Select.
- i18n: Namespace `events` in `messages/de.json` + `en.json` ergänzen.

## Konventionen / Stolperfallen (aus der letzten Session gelernt)

- ruff B008: `Query(default=None)` mit UUID/datetime/date-Annotation braucht
  `# noqa: B008` (str/int nicht).
- mypy `--strict` hat ~68 vorbestehende Fehler repo-weit — neue Fehler nach bestehendem
  Muster (z.B. `-> dict`, `auth.tenant_id` UUID|None) sind kein Regressionskriterium.
- API-Responses mit Decimal/Datum: `model_dump(mode="json")`.
- Tests laufen gegen Postgres auf localhost:5433 (docker compose muss laufen).
- Checks: `cd backend && uv run ruff check . && uv run pytest -q` und
  `cd apps/web && npm run typecheck && npm run lint && npx vitest run && npm run build`.
- Migration im Container anwenden: `docker compose exec -T backend uv run alembic upgrade head`.

## Danach (Roadmap)

1. **Mobile-Angleichung (iOS)**: Die App spricht direkt mit der REST-API und nutzt
   bisher nur Competitions/Sessions/Entries. Nichts ist kaputt (neue Member-Felder sind
   additiv, Codable ignoriert unbekannte Keys), aber es fehlen:
   - Events (Kalender + Anmeldung) — höchste Priorität auf Mobile
   - Beiträge: „Meine offenen Posten" als Mitglieder-Self-Service
   - Bankdaten/SEPA-Mandat im Mitgliederprofil
2. Gruppen/Abteilungen (Sparten, Mannschaften)
3. Schützen-Modul: Schießbuch (WaffG-relevant), Standaufsicht — als per Tenant
   aktivierbares Modul designen
4. mypy-strict-Cleanup (eigener Task)
