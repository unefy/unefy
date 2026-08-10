# Roadmap: Gesamtvorgehen nach Bestandsaufnahme

Stand 2026-08-09, auf Basis der vollständigen Inventur (Backend, Web, Android)
und des verifizierten Prozessmodells Termin ↔ Einheit ↔ Wettkampf.

## Was erledigt ist (Fortschritt, nicht Plan)

**Phasen 0 bis 4 sind durch.** Dashboard statt Scaffold-Startseite, Termine,
Beiträge samt SEPA-Export, Wettkämpfe, Command-Palette; in der App der Weg von
der Serie zum Durchgang, dazu der eigene Stand als Selbsteintrag und der
Check-in-Hinweis.

**Aus Phase 5 ist der größte Posten erledigt:** die Bescheinigung ist ein
druckbares Dokument, ihr QR führt auf eine öffentliche Prüfseite statt auf
JSON, die gezählten Termine lassen sich als Anlage mitgeben, und die
Verbandsmitgliedschaft steht mit drauf.

Die Entscheidungen E1 bis E3 sind getroffen und umgesetzt (siehe Tabelle
unten). E4 — iOS parken — ist weiterhin unbeantwortet.

**Zwei Erkenntnisse aus dem Betrieb, die keine Phase waren:** Der Login auf
Prod ist gebrochen, solange `COOKIE_DOMAIN` den Container nicht erreicht; das
Backend verweigert seit `840c648` den Start in dieser Konstellation, statt
eine unbenutzbare Anmeldung auszuliefern. Und eine neue Abhängigkeit erreicht
weder den Web- noch den Backend-Container von allein — beide halten ihre
Installation in einem Volume.

## Ausgangslage in einem Absatz

Das Backend ist für fast alle Domänen fertig (inkl. SEPA-Export, Events,
Competitions, Durchgang→Kalender). Die Android-App ist der vollständigste
Client. Das Web — laut Architekturanspruch der vollumfängliche Client — hat
drei tote Sidebar-Links (`/events`, `/competitions`, `/dues`), eine
Template-Startseite und kein UI für den fertigen SEPA-Export. Die
Prozessebenen (Anmeldung / Anwesenheit / Ergebnis, verbunden über den Termin
als Hub) sind im Backend sauber verdrahtet; es fehlen Clients, die den
Prozess zu Ende fahren.

## Leitentscheidung für die Reihenfolge

**Web zuerst dort, wo fertige Backend-Arbeit unbedienbar ist; App nur dort,
wo ein kleiner Eingriff einen toten Prozesspfad öffnet.** Neue Backend-Domänen
(Public API, Webhooks, Passkeys) kommen erst, wenn die Client-Parität steht.

## Offene Entscheidungen (blockieren einzelne Phasen, nicht den Start)

| # | Frage | Empfehlung | Betrifft |
|---|---|---|---|
| E1 | Serie ↔ Check-in koppeln? | Nein, nur weicher Hinweis „noch nicht eingecheckt" bei offener Einheit | Phase 4 |
| E2 | Einsamer Schütze am eigenen Stand (§14-Tag heute nicht abbildbar) | Selbsteintrag auch für den eigenen Stand zulassen (`assurance=low`, wie extern), Kennzeichnung „selbst geführt" bleibt | Phase 4 |
| E3 | Wettkampf-Ergebniserfassung: wo? | Verwaltung + manuelle Ergebnisse im Web; Serien-Erfassung gegen Durchgang in der App | Phasen 3+4 |
| E4 | iOS | Offiziell parken (README-Notiz), keine Angleichungsarbeit bis Web-Parität steht | — |

## Phase 0 — Sofortmaßnahmen (klein, diese Woche)

1. **Uncommitted i18n committen**: `values-en` für attendance (komplett, Key-Satz
   verifiziert deckungsgleich) und die Revoke-Strings in members. Damit ist die
   App durchgängig zweisprachig.
2. **Tote Sidebar-Links ausblenden** bis die jeweilige Seite existiert — kein
   Klick darf ins 404 führen. Kommen pro Phase zurück.
3. **Startseite entstubben**: minimales echtes Dashboard statt Scaffold-Template
   („Project ready!" ist Redirect-Ziel jedes Logins). Erste Ausbaustufe reicht:
   heutige/kommende Einheiten, Mitgliederzahl nach Status, offene Beiträge
   (Summary-Endpoint existiert). Wächst mit den späteren Phasen.
4. **Doku-Leiche fixen**: Ist-Zustand in `event-competition-link.md`
   korrigieren (Web-`/events` existiert seit dem Rebuild nicht mehr).

## Phase 1 — Web: Termine (der Hub) — größter Einzelposten

Backend zu 100 % fertig (10 Endpoints), Android als Funktions-Referenz.

- `/events`: Liste (Bevorstehend/Vergangen), Anlegen/Bearbeiten/Löschen.
- `/events/[id]`: Detail mit RSVP-Verwaltung (Selbst-An-/Abmeldung,
  Fremdanmeldung durch Vorstand, Warteliste), Kapazität, Teilnehmerliste.
- **Hub-Einstiege** (der eigentliche Zweck): Sektion „Anwesenheit" mit
  verknüpften Einheiten + Zähler, „Einheit starten"
  (`POST /events/{id}/attendance-session`, idempotent), Link in die
  bestehende `/attendance/[id]`-Seite; Wettkampf-Badge bei gesetztem
  `competition_id`.
- Kein Quick-Look-Panel — Liste → Detailseite (abgestimmte Konvention).
- i18n de+en, Server Actions nach bestehendem Muster, Tests.
- Sidebar-Link `/events` wieder aktivieren.

Danach ist der Prozess „Übungsabend" erstmals in einem Client vollständig
sichtbar (Termin → Einheit → Records → Abschluss).

## Phase 2 — Web: Beiträge & SEPA — fertigstes Backend, null UI

Kassenwart-Kernnutzen; 18 Backend-Endpoints ohne Oberfläche.

- `/dues`: Übersicht mit Summary (offen/bezahlt/storniert), Filter,
  Zahlungsaktionen (`pay`/`cancel`/`reopen`).
- Beitragsarten-CRUD und Zuordnungen (Mitglied ↔ Beitragsart).
- **Beitragslauf** (`POST /generate`) mit Vorschau/Bestätigung.
- **SEPA-Export-Button** (pain.008-XML liegt fertig im Backend) inkl.
  Gläubiger-ID-Check aus den Vereinsstammdaten.
- Mitgliedsformular: Mandatsfelder ergänzen (`sepa_mandate_reference`,
  `sepa_mandate_date` sind im Typ, fehlen im Formular) — ohne Mandat kein
  seriöser Lastschriftlauf.
- Sidebar-Link `/dues` wieder aktivieren.

## Phase 3 — Web: Wettkämpfe — Verwaltung fehlt überall

Einziger Bereich, in dem auch Android nur lesend ist.

- `/competitions`: Liste, CRUD (Art, Wertungsmodus, Disziplinen).
- Durchgänge verwalten, inkl. Haken „als Termin in den Kalender"
  (`create_calendar_event` ist backendseitig komplett fertig).
- Scoreboard-Ansicht, Ergebnisliste mit manueller Erfassung/Korrektur (E3).
- „Freies Training" in der Liste kenntlich machen oder filtern.
- Sidebar-Link `/competitions` wieder aktivieren.

## Phase 4 — App + Backend: den Prozess schließen (klein, hoher Wert)

1. **Serie → Durchgang** (der tote Pfad): Einstieg „Serie erfassen" im
   Wettkampf-/Termin-Detail der App, reicht `RecordShotsKey(sessionId=…)`
   durch — die API akzeptiert `session_id` bereits. Erst damit hat das
   Scoreboard einen bedienbaren Befüllungsweg.
2. **Self-Read Schießdetails**: `GET /modules/shooting/me/records`
   (bekannte Lücke aus termin-einheit-nachweis.md) — Mitglied kann Details
   eigener externer Einträge nachträglich lesen/korrigieren.
3. **E1**: Hinweis „noch nicht eingecheckt" beim Serien-Speichern während
   einer offenen Einheit.
4. **E2**: eigener Stand als Selbsteintrag (kleine Lockerung der CHECKs +
   App-Formular).

## Phase 5 — Self-Service & Lückenschluss Web

- ~~Öffentliche **Verifikationsseite** und PDF-Ausgabe der Bescheinigung~~ —
  erledigt, inklusive optionaler Terminliste und Verbandsdaten.
- **Paginierung** statt des 100er-Caps in Mitglieder- und Anwesenheitslisten.
  Der dringendste Rest: bei 26 Testmitgliedern unsichtbar, bei 240 ein
  Datenverlust in der Ansicht.
- `/my` ausbauen: eigene Anwesenheit/Schießtage, eigene Ämter,
  Event-Anmeldungen; Mitgliederverzeichnis (`/members/directory`) fürs Web.
- **Spartenverwaltung** in den Einstellungen (heute nur beim Onboarding).
- RSVP ↔ Anwesenheit-Spiegel am Termin („angemeldet, nicht gekommen") —
  reine Leseansicht, war als A4 geparkt.

## Noch nicht eingeplant: der inhaltliche Ausbau

Gegenüber modernen Vereinsverwaltungen fehlen ganze Bereiche: Kommunikation
(Rundmails an Mitglieder oder Abteilungen), Dokumentenablage, Gruppen und
Mannschaften, Auswertungen. Das ist mehr als eine Phase und gehört geplant,
bevor daran gebaut wird.

## Offene Fragen an den Verband (nicht durch Code lösbar)

Ob eine digitale Bescheinigung überhaupt akzeptiert wird, entscheidet der
Verband (BDS/DSB), nicht die Behörde — er stellt die Bedürfnisbescheinigung
aus, auf die sich die Behörde stützt. Mehrere vergleichbare Apps schreiben
deshalb dazu, dass sie den Papiernachweis nicht ersetzen. Offen sind: akzeptiert
der Verband die digitale Form, und gibt es ein vorgeschriebenes Formular? Mit
dessen Vorgabe lässt sich das PDF danach bauen. Das qualifizierte Siegel nach
eIDAS (`seal` ist im Modell reserviert) ist der Schritt, der das letzte
technische Argument dagegen ausräumt.

## Phase 6 — Plattform & Ausbau (nach Parität)

- Admin-Bereich: Vereine/Benutzer verwalten (heute read-only), `DELETE /club`-UI.
- Benutzerprofil-/Kontoseite.
- Geparkte Einstellungsseiten (Kontakt, Vorgaben, Gebühren, Zahlung).
- Backend-Roadmap: Public API + API-Keys, Webhooks, Passkeys/Apple
  OAuth/MFA — erst hier, bewusst zuletzt.

## Nicht vergessen (Querschnitt, gilt in jeder Phase)

- Tests nach Pyramide, Regressionstest „rot gesehen" (Konvention).
- Ein pytest-Prozess gegen die geteilte `unefy_test`-DB.
- Zeitzonen: Server rechnet in der Vereins-Zeitzone.
- shadcn-Registry vor Eigenbau prüfen.
- i18n de+en für alles Neue, keine Quick-Look-Panels.
