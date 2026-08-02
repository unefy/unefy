# Plan: Multi-Tenancy, Sportarten und Schießsport-Modul

Neuentwurf des Backend-Datenmodells. Anlass: Das Web-Frontend wird ohnehin neu gebaut,
und das bestehende Schema ist implizit schießsport-geprägt, obwohl viele Vereine
unterschiedlicher Sportarten das Produkt nutzen sollen.

## Abgestimmte Entscheidungen

| Frage | Entscheidung |
|---|---|
| Reset-Tiefe | Migrationen squashen, DB wegwerfen. Keine Abwärtskompatibilität. |
| Sport-Fokus | Echt multi-sport — kein Sport ist im Kern privilegiert. |
| Referenzkunde | Der eigene Schützenverein. Das Schießsport-Modul muss vollständig sein. |
| Sportart → Defaults | Einmalig kopieren beim Onboarding, danach frei editierbar. |
| Sparten | Modell sieht sie vor, UI blendet sie aus (Referenzverein hat keine). |
| Beitritt zu Verein | E-Mail-Einladung **und** selbst neuen Verein anlegen. |
| Mannschaftssport | Nicht im ersten Wurf. Diskriminator wird trotzdem eingebaut. |
| Schießsport-Modul | Schießnachweis §14 WaffG, WBK/Waffenbesitz, Verbandsmeldung DSB/BDS. |

## Leitprinzipien

1. **Der Kern kennt keine Sportart.** Mitglieder, Beiträge, Events, Wettkämpfe
   funktionieren für jeden Verein gleich.
2. **Sportspezifisches lebt in Modulen.** Ein Modul bringt eigene Tabellen, Endpoints
   und Screens mit. Es wird pro Verein aktiviert, nicht per `if sport == "shooting"`
   im Kern verstreut.
3. **Generisch heißt nicht dünn.** Die Multi-Sport-Öffnung darf die Schießsport-Features
   nicht verwässern — sie ist der Grund für die Modulgrenze, nicht für Verzicht.
4. **Daten in die DB, Verhalten in den Code.** Alles, was nur benannt, sortiert,
   übersetzt oder gruppiert werden muss, ist über die UI pflegbar. Nur was einen
   Codepfad *voraussetzt*, bleibt eine Code-Konstante — die DB referenziert sie dann.

   | Über die UI pflegbar (DB) | Code-Konstante |
   |---|---|
   | Sportarten, Disziplin-Katalog, Einheiten | Rollen (gaten Autorisierung) |
   | Verbände, Kategorien | `scoring_mode` (braucht Ranking-Implementierung) |
   | Altersklassen und ihre Grenzen | `competition.format` (braucht Aggregation) |
   | Beitragsarten-Vorlagen, Mitgliedsstatus | Module (bringen Tabellen + Screens mit) |
   | §14-Schwellwerte, Nachweis-Layout | |

   Faustregel: Wenn ein neuer Wert ohne Deployment funktionieren soll, gehört er in die
   DB. Wenn ein neuer Wert ohne passenden Code sinnlos oder kaputt wäre, gehört er in
   den Code.

## Ebenenmodell

Vier Konzepte, die sauber getrennt bleiben müssen:

- **User** — globale Identität (E-Mail, OAuth). Existiert unabhängig von Vereinen.
- **TenantMembership** — *Zugang*: welcher User darf in welchem Verein was.
  Rollen `owner`, `admin`, `board`, `member`.
- **Member** — *Vereinsmitglied*: die verwaltete Person. Die meisten Mitglieder haben
  nie einen Account. Optionaler `user_id`-Link für das Self-Service-Portal.
- **Division (Sparte)** — trägt die Sportart.

Die Trennung Member ↔ TenantMembership ist im bestehenden Code bereits korrekt umgesetzt
(`models/member.py`, Docstring "Distinct from User (login account)", `user_id` nullable)
und wird unverändert übernommen. Sie ist hier festgehalten, damit sie beim Neubau nicht
versehentlich zusammenfällt.

## Plattform-Administration

Es gibt zwei Admin-Ebenen, die heute nicht getrennt sind — alle Rollen sind
tenant-scoped:

- **Vereins-Admin** (`owner`/`admin`) — konfiguriert den eigenen Verein.
- **Plattform-Admin** — pflegt globale Stammdaten: Sportarten, Disziplin-Katalog,
  Verbände, Default-Sets. Steht über allen Tenants.

**Umgesetzt (2026-08-01):** `users.is_superuser`, die Dependency
`require_platform_admin`, der Endpoint-Bereich `/api/v1/admin/…`, ein
append-only `admin_audit_log` und Impersonation mit Vollzugriff. Die Web-Oberfläche
liegt unter `apps/web/app/(admin)/`.

Das Flag ist über keinen HTTP-Endpoint setzbar — es gibt keine tenant-scoped Rolle,
die es implizieren dürfte. Vergabe ausschließlich über
`backend/scripts/create_superuser.py` (`mise run superuser -- grant <email> --create`),
was Shell-Zugriff auf das Backend voraussetzt. Das Skript weigert sich, den letzten
Plattform-Admin zu entfernen, weil es keinen Weg zurück in den Bereich gäbe.

Der Bereich ist sicherheitskritisch — er umgeht per Definition die Tenant-Isolation.
Rollenprüfung und Audit-Logging gehören hier zwingend in Tests.

## Sportarten: Tabelle statt Konstante

```
sports (global)     key (unique), name, description, icon, sort_order, is_active
                    modules  String[]   verweist auf im Code vorhandene Module
```

Über die Plattform-Admin-UI pflegbar: neue Sportart anlegen, benennen, sortieren,
deaktivieren, Katalog befüllen — alles ohne Deployment.

`modules` ist die eine Stelle, an der DB auf Code zeigt: Ein Modul bringt Tabellen,
Endpoints und Screens mit und kann nicht über die UI entstehen. Die Zuordnung
„Sportart X nutzt Modul `shooting`" ist dagegen reine Konfiguration. Die API validiert
beim Speichern gegen die im Code registrierten Modulnamen, damit kein toter Verweis
entsteht.

Start mit wenigen Sportarten, deren Kataloge inhaltlich gefüllt sind, plus einer
Auffangoption mit leerem Katalog. Zwölf Sportarten mit dünnen Defaults sind schlechter
als drei mit guten — der Unterschied ist jetzt nur, dass die vierte kein Release mehr
braucht.

### Was daraus folgt

Der Disziplin-Katalog wird von einer Python-Seed-Datei zu echten, über die UI pflegbaren
Stammdaten:

- `app/core/discipline_seeds.py` (28 Einträge) wird zur **Initial-Befüllung** der
  Tabelle, nicht mehr zur Quelle der Wahrheit. Der heutige `seed_disciplines()`-Aufruf
  bei jedem App-Start entfällt — sonst überschreibt oder verwirrt er, was der
  Plattform-Admin gepflegt hat.
- `catalog_disciplines` bekommt volle CRUD-Endpoints unter `/api/v1/admin/…`.
- Ebenso `catalog_units` (global) als sportartabhängige Default-Sets — heute ist
  `MEASUREMENT_UNIT_SEEDS` eine flache Code-Liste für alle Sportarten.
- `federation` und `category` werden dabei besser eigene kleine Tabellen als freie
  Strings, damit die UI Auswahllisten statt Texteingaben zeigen kann.

## Kern-Schema

### Identität und Zugang

```
users                 id, email (unique), name, image, email_verified, locale, google_id
tenants               Stammdaten, Kontakt, Adresse, Recht/Steuer, SEPA,
                      Mitgliedsnummern-Schema, has_divisions
tenant_memberships    user_id, tenant_id, role, is_active, joined_at
invitations           tenant_id, email, role, token, expires_at, accepted_at, invited_by
```

### Vereinsstruktur

```
divisions (tenant)    name, sport_key, is_primary
members (tenant)      Stammdaten, Mitgliedschaft, SEPA, user_id (nullable)
```

`divisions` existiert immer. Ein Einspartenverein bekommt beim Onboarding genau eine
Zeile (`is_primary = true`, Name = Vereinsname), und `tenants.has_divisions = false`
blendet die Sparten-UI aus. Dadurch gibt es **einen** Codepfad statt zwei, und ein Verein
kann später Sparten einschalten, ohne dass Daten migriert werden müssen.

Mitglied ↔ Sparte wird bewusst noch nicht verknüpft — der Referenzverein braucht es nicht,
und die Beitragslogik wird dadurch erheblich komplexer. Nachrüstbar als n:m-Tabelle.

### Katalog

```
catalog_disciplines (global, gepflegt vom Plattform-Admin)
    sport_key, slug, name, short_name, description
    federation           DSB | BDS | DLV | ...
    category             Gruppierung innerhalb des Verbands
    unit                 Ringe | Sekunden | Meter | ...
    scoring_mode         highest_wins | lowest_wins | fastest_time
    precision            Nachkommastellen
    attributes  JSONB    sportspezifisch: caliber, target_type, distance, shot_count
    is_official, is_active
```

`federation` und `category` bleiben echte Spalten — sie sind nicht schießsportspezifisch
(jeder Sport hat Verbände und Disziplingruppen) und werden zum Filtern und Indizieren
gebraucht. Nur wirklich Sportspezifisches geht nach `attributes`.

```
units (tenant)         name, symbol, is_active
disciplines (tenant)   name, short_name, unit, scoring_mode, sport_key, is_active
```

Beim Onboarding werden passend zur gewählten Sportart Einträge aus dem globalen Katalog
in die tenant-eigenen Tabellen kopiert. Danach gehören sie dem Verein und sind frei
editierbar. Ein späterer Nachimport bleibt möglich.

**Offener Punkt:** `UniqueConstraint(tenant_id, name)` muss als *partieller* Index auf
`deleted_at IS NULL` angelegt werden. Im aktuellen Stand ist er das nicht, wodurch das
Neuanlegen eines soft-gelöschten Namens einen `IntegrityError` (500) statt eines 409
auslöst.

### Wettkampf

```
competitions (tenant)  name, format, season, discipline_ids, ...
sessions (tenant)      competition_id, name, date, location, discipline
entries (tenant)       session_id, member_id, score, details JSONB
```

`format` ist der Diskriminator: im ersten Wurf nur `measured` (gemessene Einzelleistung —
ein numerischer Wert, `scoring_mode` bestimmt die Rangfolge). Mannschaftsbegegnungen
(zwei Seiten, Sieg/Unentschieden/Niederlage, Tabelle) kommen später als zweiter Wert
dazu, ohne das Schema aufzubrechen.

### Finanzen und Termine

`fee_types`, `member_fees`, `dues`, `events`, `event_registrations` werden inhaltlich
unverändert übernommen. `fee_types` sollte beim Onboarding sinnvolle Defaults bekommen —
heute wird gar nichts geseedet.

## Schießsport-Modul

Eigene Tabellen, eigene Endpoints unter einem Modul-Präfix, aktiviert über die
Sportart des Vereins.

### Schießnachweis (§14 WaffG)

```
shooting_attendances (tenant)
    member_id, date, discipline_id (nullable), supervisor_member_id (nullable),
    source          manual | competition_entry
    entry_id        (nullable, wenn aus einem Wettkampf abgeleitet)
```

Auswertung: Teilnahmen pro Mitglied in einem rollierenden 12-Monats-Fenster, mit
konfigurierbaren Schwellwerten pro Verein statt fest kodierter Zahlen. Ausgabe als
druckbarer Nachweis für die Behörde.

> Die exakten gesetzlichen Schwellwerte und Fristen sind vor der Implementierung mit der
> aktuellen Gesetzeslage und der zuständigen Behörde abzugleichen. Sie gehören in die
> Vereinskonfiguration, nicht in den Code — auch weil sich Rechtslage und
> Behördenpraxis ändern.

Wettkampf-Entries sollen automatisch als Teilnahme zählen, damit nichts doppelt erfasst
wird.

### Waffenbesitz

```
firearm_licenses (tenant)   member_id, license_type, license_number, issued_at,
                            issuing_authority, notes
firearms (tenant)           license_id, category, caliber, manufacturer, model,
                            serial_number, acquired_at, disposed_at
```

Enthält personenbezogene Daten besonderer Sensibilität — Zugriff nur für `owner`/`admin`,
und die Rollenprüfung gehört in Tests abgesichert.

### Verbandsmeldung DSB/BDS

Export von Melde- und Startberechtigungslisten. Braucht faktisch eine Alterseinstufung
(Schüler/Jugend/Junioren/Herren/Damen/Senioren, stichtagsabhängig) — die war in der
Abstimmung nicht ausgewählt.

**Offener Punkt:** Vorschlag, Altersklassen mitzunehmen — als `age_classes`-Tabelle
(Name, Von-/Bis-Alter, Geschlecht, Stichtagsregel, Sportart), gepflegt vom
Plattform-Admin und beim Onboarding in den Verein kopiert. Die Einstufung selbst wird
aus `birthday` berechnet, nicht gespeichert. Klassengrenzen ändern sich mit
Verbandsordnungen — genau der Fall, der nicht in den Code gehört.

## Onboarding

1. OAuth- oder Magic-Link-Login → User existiert, noch keine Membership.
2. `/onboarding`: Vereinsname, Sportart, Adresse/Kontakt.
3. `POST /auth/onboarding/create-club`:
   - Tenant anlegen, **Slug aus dem Vereinsnamen** (heute zufällig `club-<hex>`),
     Kollisionen mit Suffix
   - eine `division` (`is_primary`, Name = Vereinsname)
   - `member_statuses` (locale-abhängig)
   - `units` + `disciplines` aus dem Katalog **der gewählten Sportart**
   - `fee_types`-Defaults
   - `TenantMembership` mit Rolle `owner`
   - Session-Rotation auf den neuen Tenant

**Umgesetzt (2026-08-01):** `create_club` nimmt `has_divisions` und eine Liste von
Sparten (`name` + `sport_key`) entgegen, legt Tenant, Divisions und Owner-Membership an
und seedet die Einheiten aus `catalog_units` der gewählten Sportarten (dedupliziert über
alle Sportarten). Der Slug entsteht aus dem Vereinsnamen inklusive Umlaut-Transliteration
(`Schützenverein …` → `schuetzenverein-…`), bei Kollision mit Zähler-Suffix.

Die Sperre `ConflictError("User already has a club")` ist entfernt — ein Nutzer kann
mehrere Vereine besitzen. Missbrauch begrenzt weiterhin das Rate-Limit (5/h pro Nutzer).

Die flache `MEASUREMENT_UNIT_SEEDS`-Liste, die jedem Verein Ringe *und* Tore *und* Körbe
gab, wird von `create_club` nicht mehr benutzt. Die Konstante existiert noch für
`app/core/seeds.py`-Altlasten und sollte beim Migrations-Squash entfallen.

Die Onboarding-Oberfläche liegt unter `apps/web/app/onboarding/` und liest die
Sportarten über `GET /api/v1/sports` — authentifiziert, aber ohne Tenant-Zwang, weil der
Aufrufer per Definition noch keinen Verein hat.

## Einladungen

```
POST   /invitations              (owner/admin)  E-Mail + Rolle, Token, Versand
GET    /invitations              (owner/admin)  offene Einladungen
DELETE /invitations/{id}         (owner/admin)  zurückziehen
POST   /invitations/{token}/accept              angenommen → Membership
```

Token einmalig verwendbar und mit Ablaufdatum. Annahme setzt einen eingeloggten User
voraus; ist noch keiner da, führt der Link durch Login und danach zurück zur Annahme.
Bereits bestehende aktive Membership → 409.

Optional: beim Annehmen ein vorhandenes `Member` mit gleicher E-Mail verknüpfen, statt
eine reine Zugangs-Membership ohne Mitgliedsdatensatz zu erzeugen.

## Mobile

`auth_mobile.py` wählt heute hart die älteste Membership
(`order_by(joined_at.asc()).limit(1)`). Mit mehreren Vereinen ist das falsch — die App
braucht eine Tenant-Auswahl analog zu `switch-tenant`, und der JWT-`tid`-Claim muss
wechselbar sein.

## Migrationsstrategie

Die 18 bestehenden Migrationen werden zu einer Initial-Migration zusammengefasst. Kein
Backfill, keine Datenübernahme.

**Vorher zu klären:** Die iOS-App konsumiert Competitions/Sessions/Entries. Wenn dort
Daten liegen, die erhalten bleiben sollen, braucht es einen Export vor dem Reset.

## Reihenfolge

1. Kaputten HEAD reparieren (Commit `8b96754` referenziert die uncommitteten Module
   `app.core.seeds` und `app.models.catalog` — frischer Clone bricht), `backend/package*`
   und `backend/node_modules/` entfernen
2. Kern-Schema inkl. `sports`, `catalog_*`, `is_superuser`; Initial-Migration
3. Plattform-Admin: `require_platform_admin`, `/api/v1/admin/…` CRUD für Sportarten,
   Katalog, Einheiten, Altersklassen; Initial-Befüllung aus den heutigen Seed-Dateien
4. Onboarding: Sportart-Auswahl, Mehrfach-Vereine, sportartabhängiges Seeding
5. Einladungs-Flow inkl. E-Mail
6. Schießsport-Modul: Schießnachweis → WBK → Verbandsmeldung
7. Frontend: Onboarding-Wizard, Vereins-Switcher, Einladungs-UI
8. Plattform-Admin-UI
9. Mobile: Tenant-Auswahl

Schritt 3 wächst durch die UI-Pflegbarkeit spürbar — es ist im Kern ein zweiter,
kleiner Admin-Bereich mit eigenen Screens. Falls das den ersten Wurf zu breit macht:
Tabellen und Endpoints jetzt bauen, die Admin-UI nachziehen und die Stammdaten
übergangsweise per Seed befüllen. Das Datenmodell ist dann schon richtig.

## Offene Punkte

- Reicht `users.is_superuser` oder braucht die Plattform-Admin-Ebene eigene Rollen?
- Altersklassen mitnehmen? (siehe oben — Vorschlag: ja, als Stammdaten)
- Exakte §14-Schwellwerte und Nachweisformat mit dem Verein abgleichen
- Welche Sportarten außer Schießsport zum Start, und wer füllt deren Kataloge
- iOS-Datenexport vor dem DB-Reset nötig?
- Soll das Schießsport-Modul für Nicht-Schützenvereine manuell aktivierbar sein
- Übersetzung UI-pflegbarer Stammdaten: Sportarten und Disziplinen brauchen Labels in
  de/en. Eigene Spalten, JSONB oder Übersetzungstabelle?
