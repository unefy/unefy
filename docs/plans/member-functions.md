# Plan: Funktionen / Ämter im Verein

Stand 2026-08-05. Vereinsämter (Vorsitzender, Kassier, Schriftführer,
Jugendleiter, Schützenmeister, …) als eigenes Konzept — getrennt von den
Auth-Rollen (`TenantMembership.role`), die weiterhin nur Berechtigungen steuern.

## Leitplanken

1. **Pro Verein komplett flexibel.** Der globale Katalog liefert nur den
   Startvorschlag beim Onboarding. Danach gehört die Funktionsliste dem Verein:
   umbenennen, löschen, eigene Funktionen frei anlegen — ohne Bezug zum
   Katalog. Gleiche Mechanik wie `CatalogUnit` → `measurement_units`
   (Kopie by value, keine FK zurück).
2. **Zeitliche Zuordnung mit Wiederholung.** Ein Mitglied kann dieselbe
   Funktion mehrfach innehaben (2025 Kassier, 2026 nicht, ab 2027 wieder).
   Jede Amtszeit ist eine eigene Zeile mit `valid_from`/`valid_to`.
   `valid_to = NULL` heißt „aktuell im Amt". Historie wird nie gelöscht,
   nur beendet.
3. **Scope Verein vs. Sparte.** Funktionen haben ein `level` (`club` |
   `division`). Zuweisungen auf `division`-Ebene tragen eine `division_id`;
   dieselbe Funktion kann je Sparte getrennt besetzt sein. Vereine ohne
   `has_divisions` sehen von `division`-Funktionen nichts.
4. **Funktion ≠ Berechtigung.** Eine Katalogfunktion kann eine *empfohlene*
   Auth-Rolle tragen (Kassier → `board`). Das UI schlägt sie beim Zuweisen
   vor, koppelt aber nie automatisch.

## Datenmodell

### `catalog_functions` (global, wie `sports`/`catalog_units`)

| Feld | Typ | Bemerkung |
|---|---|---|
| `id` | UUID | |
| `sport_id` | UUID? → sports, SET NULL | NULL = allgemeines Amt für alle Sportarten |
| `key` | String(100) | stabil, für Seeds/Idempotenz |
| `name` | String(255) | deutscher Anzeigename als Default |
| `level` | String: `club` \| `division` | |
| `suggested_role` | String? | `owner`/`admin`/`board`/`member`, nur Vorschlag |
| `sort_order` | int | |

Gepflegt von Plattform-Admins (Admin-Bereich, analog Sportarten/Disziplinen).
Seed-Inhalte in `backend/app/core/function_seeds.py`:

- Allgemein: 1. Vorsitzende:r, 2. Vorsitzende:r, Kassier, Schriftführer:in,
  Beisitzer:in, Kassenprüfer:in, Jugendleiter:in, Abteilungsleiter:in (`division`).
- Schießsport: Schützenmeister, Sportleiter, Waffenwart, Schießstandaufsicht,
  Damenleiterin.

### `functions` (tenant-scoped, die Liste des Vereins)

`TenantModel + AuditMixin`, Tabelle `functions`:

| Feld | Typ | Bemerkung |
|---|---|---|
| `name` | String(255) | UniqueConstraint (tenant_id, name) |
| `level` | String: `club` \| `division` | |
| `suggested_role` | String? | |
| `sort_order` | int | |
| `is_active` | bool | deaktivieren statt löschen, wenn Zuweisungen existieren |

Löschen ist erlaubt, solange keine `member_functions`-Zeilen (auch historische)
darauf zeigen; sonst 409 mit Hinweis auf Deaktivieren — gleiche Semantik wie
Sportarten mit Disziplinen.

### `member_functions` (Zuweisung / Amtszeit)

`TenantModel + AuditMixin`, Tabelle `member_functions`:

| Feld | Typ | Bemerkung |
|---|---|---|
| `member_id` | UUID → members, CASCADE | |
| `function_id` | UUID → functions, RESTRICT | |
| `division_id` | UUID? → divisions, SET NULL | Pflicht, wenn Funktion `level=division` |
| `valid_from` | date | Pflicht |
| `valid_to` | date? | NULL = aktuell |
| `note` | String(500)? | z. B. „kommissarisch" |

Constraints/Validierung:

- Index (tenant_id, member_id), (tenant_id, function_id, division_id).
- Überlappungsschutz **im Service, nicht als DB-Exclusion-Constraint**:
  dasselbe Mitglied darf dieselbe Funktion (gleiche `division_id`) nicht in
  überlappenden Zeiträumen doppelt haben. Mehrere *verschiedene* Mitglieder
  gleichzeitig in derselben Funktion sind erlaubt (Beisitzer, Kassenprüfer).
- `valid_to >= valid_from` (Pydantic).
- Kein Soft-Delete-Bedarf: Historie ist das Feature; echtes Löschen nur für
  Fehleingaben, geht durchs Audit-Log.

## Backend-Schritte

1. **Migration + Models**: `catalog_functions`, `functions`,
   `member_functions` (`backend/app/models/function.py`), Seed der
   Katalogfunktionen in der Migration (wie Sports-Migration 2026-08-01).
2. **Repositories/Services**: `FunctionRepository`, `MemberFunctionRepository`
   (tenant-scoped via Basisklasse), `FunctionService` mit
   Überlappungsprüfung + Level/Division-Konsistenz.
3. **API** (`backend/app/api/v1/functions.py`):
   - `GET/POST /functions`, `PATCH/DELETE /functions/{id}` — Rolle `admin`.
   - `GET /members/{id}/functions` (Historie, sortiert nach `valid_from` desc),
     `POST /members/{id}/functions`, `PATCH/DELETE
     /members/{id}/functions/{assignment_id}` — Rolle `board`.
   - `GET /functions/holders?at=YYYY-MM-DD` — Besetzungsliste (wer hat aktuell/
     zum Stichtag welches Amt), Rolle `member` lesbar (Vorstandsliste ist im
     Verein öffentlich).
4. **Onboarding-Seeding**: in `OnboardingService.create_club()` neben
   `_seed_units()` ein `_seed_functions()` — kopiert allgemeine + zu den
   gewählten Sportarten passende Katalogfunktionen; `division`-Funktionen nur
   bei `has_divisions=True`. Dedupe by name wie bei Units.
5. **Sync/Spiegel**: Funktionen + Zuweisungen in den Live-Sync-Stream
   aufnehmen (gleiches Muster wie members/events), damit die Android-App den
   Spiegel bekommt — kann als eigener Folgeschritt laufen.

## Web-Schritte

1. **Einstellungen → Funktionen** (`/settings/functions`): DataTable mit
   Name, Ebene, empfohlener Rolle, aktiv; Dialog zum Anlegen/Bearbeiten
   (shadcn, Muster Einheiten/Disziplinen). Hier entstehen die „komplett
   eigenen" Funktionen.
2. **Mitglieder-Detail**: neue Sektion „Funktionen" — aktuelle Ämter oben,
   Historie darunter (Zeitraum, Funktion, ggf. Sparte, Notiz). Zuweisen-Dialog:
   Funktion, Sparte (wenn `level=division`), von/bis, Notiz; beim Speichern
   Hinweis, wenn `suggested_role` über der aktuellen Auth-Rolle des verknüpften
   Zugangs liegt. Amtszeit beenden = `valid_to` setzen, nicht löschen.
3. **Vorstandsliste**: Seite oder Dashboard-Karte „Funktionsträger" aus
   `GET /functions/holders`, mit Stichtag-Wahl (Datum) für den Blick in die
   Vergangenheit („wer war 2025 Kassier?").
4. i18n de/en für alles Neue.

## Wizard-Ausbau (danach, eigener Schritt)

Bestehendes Onboarding (`apps/web/components/onboarding/onboarding-form.tsx`)
zu drei Schritten:

1. **Struktur**: einfacher Verein / mit Abteilungen (heutiger Toggle + Sparten).
2. **Sportarten**: heutige Auswahl.
3. **Vorschau**: „Das richten wir ein" — Funktionen (abwählbar, einzelne
   entfernen), Einheiten, aktive Module. Abgewählte Funktionen werden nicht
   kopiert.

Backend: `create-club`-Payload bekommt optional `function_keys: list[str]`
(Teilmenge des Katalogs); ohne Angabe wird der volle passende Satz kopiert —
damit bleibt der Endpoint für Mobile/API ohne Wizard nutzbar.

## Tests

- Service: Überlappungsprüfung (gleiche Funktion+Sparte überlappt → 409;
  disjunkte Wiederholung 2025/2027 → ok; zwei Mitglieder parallel → ok),
  Level/Division-Konsistenz, Löschen mit Historie → 409.
- API: CRUD happy path, 403-Matrix (member darf lesen, nicht schreiben),
  Tenant-Isolation (A sieht B nicht), Stichtagsabfrage.
- Onboarding: Seeding mit/ohne Divisions, mit/ohne Sportart Schießsport,
  mit `function_keys`-Teilmenge.
- Ein pytest-Prozess (geteilte Test-DB).

## Reihenfolge

1. Backend: Modelle + Migration + Katalog-Seed
2. Backend: Services + API + Tests
3. Backend: Onboarding-Seeding
4. Web: Einstellungen + Mitglieder-Detail + Vorstandsliste
5. Wizard-Umbau (Web + `function_keys`)
6. Sync/Android-Spiegel

## Offene Fragen

- Braucht die Vorstandsliste einen Export (PDF/CSV) fürs Vereinsregister?
- Sollen Funktionsträger automatisch im Mitgliederverzeichnis (`/members/
  directory`) hervorgehoben werden?
- Ehrungen/Ehrenämter („Ehrenvorsitzender") als normale Funktion ohne Ende
  abbilden oder später eigenes Ehrungen-Modul?
