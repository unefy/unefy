# Roadmap: Gesamtvorgehen nach Bestandsaufnahme

Stand 2026-08-09, auf Basis der vollständigen Inventur (Backend, Web, Android)
und des verifizierten Prozessmodells Termin ↔ Einheit ↔ Wettkampf.

## Was erledigt ist (Fortschritt, nicht Plan)

**Phasen 0 bis 4 sind durch.** Dashboard statt Scaffold-Startseite, Termine,
Beiträge samt SEPA-Export, Wettkämpfe, Command-Palette; in der App der Weg von
der Serie zum Durchgang, dazu der eigene Stand als Selbsteintrag und der
Check-in-Hinweis.

**Phase 5 ist ebenfalls durch:** die Bescheinigung ist ein druckbares
Dokument, ihr QR führt auf eine öffentliche Prüfseite statt auf JSON, die
gezählten Termine lassen sich als Anlage mitgeben und die
Verbandsmitgliedschaft steht mit drauf; die Listen enden nicht mehr bei
Zeile 100; `/my` trägt fünf Reiter; Sparten sind nach dem Onboarding
pflegbar; und der Termin stellt Zusage und Anwesenheit nebeneinander.

Damit ist die Client-Parität hergestellt: Es gibt keine fertige Backend-Arbeit
mehr, die unbedienbar wäre. Phase 6 fragt deshalb nach fehlenden *Features*,
nicht nach fehlenden Oberflächen.

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

## Offene Fragen an den Verband (nicht durch Code lösbar)

Ob eine digitale Bescheinigung überhaupt akzeptiert wird, entscheidet der
Verband (BDS/DSB), nicht die Behörde — er stellt die Bedürfnisbescheinigung
aus, auf die sich die Behörde stützt. Mehrere vergleichbare Apps schreiben
deshalb dazu, dass sie den Papiernachweis nicht ersetzen. Offen sind: akzeptiert
der Verband die digitale Form, und gibt es ein vorgeschriebenes Formular? Mit
dessen Vorgabe lässt sich das PDF danach bauen. Das qualifizierte Siegel nach
eIDAS (`seal` ist im Modell reserviert) ist der Schritt, der das letzte
technische Argument dagegen ausräumt.

## Phase 6 — Eintritt, Einwilligung, Bescheinigung

Priorisiert am 2026-08-10 vom Nutzer, gegen die vorherige Sortierung nach
Häufigkeit. Der rote Faden ist ein anderer und ein besserer: **wie ein Mensch
Mitglied wird, was er dabei einwilligt, und was er darüber in der Hand hält.**

Kommunikation, Auswertungen, Dokumentenablage und Mannschaften bleiben in der
Liste, rücken aber dahinter (6.4 bis 6.7).

### 6.1 Digitaler Mitgliedsantrag

Heute legt ein Vorstandsmitglied neue Mitglieder von Hand an — der Beitritt
selbst findet außerhalb des Systems statt, auf Papier oder per Mail.

- Öffentliches Formular, ohne Anmeldung erreichbar, je Verein.
- Es erzeugt einen **Antrag**, kein Mitglied. Aufnahme ist ein Beschluss, und
  ein Formular fasst keine Beschlüsse: der Vorstand nimmt an oder lehnt ab,
  und erst die Annahme legt den Mitgliedsdatensatz an.
- Beitragsart und Sparte wählbar, soweit der Verein sie anbietet.
- SEPA-Mandat gleich mit erteilen — die Felder gibt es am Mitglied bereits.
- Missbrauchsschutz: Rate-Limit wie bei den Auth-Endpunkten, und ein Antrag
  darf keine Auskunft darüber geben, wer schon Mitglied ist.
- Abgelehnte und offene Anträge unterliegen einer eigenen Frist — sie sind
  Bewerberdaten, keine Mitgliederdaten.

### 6.2 Einwilligungen und Auskunft (DSGVO)

Gehört unmittelbar zu 6.1: Der Antrag ist der Moment, in dem eingewilligt
wird, und der einzige, in dem es unaufwendig ist.

Baubar und deshalb hier:

- **Einwilligungen je Mitglied** mit Zeitpunkt und Widerruf — Foto/Bild,
  Rundmail, Nennung im Verzeichnis. Heute existiert dafür kein einziges Feld.
  Sie sind **Voraussetzung für die Rundmail** aus 6.4: Wer ohne sie Serienmails
  verschickt, baut sich ein Problem ein, das später teuer wird.
- **Auskunft nach Art. 15** als Export der eigenen Daten. Die `/me`-Endpunkte
  liefern schon alles; es fehlt das Bündel.
- **Löschung nach Art. 17** im Verhältnis zu den Aufbewahrungsfristen, die pro
  Verein bereits konfigurierbar sind. Heute ist Löschen ein Soft-Delete — für
  ein Löschersuchen zu wenig.

Nicht baubar, und das gehört im Produkt auch so benannt: Datenschutzerklärung,
Verarbeitungsverzeichnis und Auftragsverarbeitungsverträge sind Vereinstext.
Ein Gerüst mit Platzhaltern können wir liefern, Rechtsberatung nicht.

### 6.3 Mitgliedsbescheinigungen

Zwei Sorten Dokument, und der Unterschied entscheidet die Bauform:

- **Vorgeschriebene Formen** (Zuwendungsbestätigung nach amtlichem Muster, die
  §14-Bescheinigung) bleiben fest gebaut. Ein Editor wäre dort eine Einladung,
  ein ungültiges Dokument zu erzeugen.
- **Freie Formen** (Mitgliedsbescheinigung) laufen über **Textvorlagen mit
  Variablen** — kein Layout-Editor, entschieden am 2026-08-10.

  Der Verein schreibt den Wortlaut und setzt Platzhalter aus einem festen,
  dokumentierten Satz: `{{mitglied.name}}`, `{{mitglied.nummer}}`,
  `{{mitglied.eintritt}}`, `{{verein.name}}`, `{{datum}}`. Gerendert wird in
  das vorhandene Ein-Seiten-Layout. Das ist sicher (keine beliebige
  Auswertung, keine Injection), vorhersagbar im Druckbild und übersetzbar —
  und der Verein ändert den Text, ohne auf ein Release zu warten.

  Die Vorlage ist **fließender Text, den der Verein selbst zusammenstellt** —
  eigene Absätze an beliebiger Stelle, Platzhalter mitten im Satz. Kein
  Formular mit zwei vorgegebenen Feldern: fest ist nur der Rahmen (Briefkopf
  oben, Fuß unten), und beides ist je Vorlage abschaltbar. „Beliebige Stelle"
  heißt dabei im Textfluss, nicht frei auf der Seite — das Druckbild bleibt
  unseres, der Inhalt gehört dem Verein.

  **Autovervollständigung** im Editor: `{{` öffnet die Liste der Variablen mit
  einer Erklärung je Eintrag. Wer den Satz nicht auswendig kennt, soll ihn
  nicht suchen müssen — und dieselbe bekannte Liste trägt die Prüfung.

  Ein unbekannter Platzhalter muss beim Speichern auffallen, nicht erst im
  fertigen PDF: eine Vorlage mit `{{mitglied.vorname}}` soll die Bearbeitung
  ablehnen, statt später eine Lücke zu drucken.

  Der Briefkopf kommt einmal aus den Einstellungen und nicht in jede Vorlage —
  Logo, Anschrift, Registernummer und Gemeinnützigkeit stehen am
  Vereinsdatensatz, `logo_url` ist da und wird bislang nirgends benutzt.

- **Prüfbar mit QR und Prüfcode**, wie der §14-Nachweis. Die `/verify`-Seite
  steht bereits; eine Bescheinigung, deren Echtheit ein Arbeitgeber nachsehen
  kann, ist mehr wert als ein PDF, das jeder in Word nachbaut. Das bedingt
  eine Ausstellungshistorie samt Widerruf — was ausgestellt wurde, muss
  festgehalten werden, sonst prüft die Seite gegen nichts.

### 6.4 Kommunikation

Rundmail an Mitglieder, Sparte, Amt, Angemeldete eines Termins, Schuldner
eines Jahres. Vorhanden ist nur ein Ein-Empfänger-Versand für Magic Links.
Versand asynchron und in Paketen, mit Historie.

**Setzt 6.2 voraus** (Einwilligungen). Offene Entscheidungen: Versandweg
(eigener SMTP vs. Dienst — Zustellbarkeit ist bei Vereinsmails das eigentliche
Problem) und die Trennung von Pflichtmitteilung und Werbung.

### 6.5 Auswertungen

Mitgliederentwicklung, Beitrags-Soll/Ist, Anwesenheitsstatistik, CSV-Export
für den Rechenschaftsbericht. Rein lesende Aggregation über vorhandene
Tabellen — verglichen mit dem Nutzen die billigste Position der Phase.

### 6.6 Dokumentenablage

Satzung, Protokolle, Formulare. Braucht als Einziges neue Infrastruktur:
Dateiablage (S3-kompatibel oder ein Volume beim Self-Hosting), Größen- und
Typprüfung, Zugriff je Rolle. Die Entscheidung über den Speicher ist eine
Betriebs-, keine Feature-Entscheidung.

### 6.7 Mannschaften

Wettkämpfe kennen heute nur Einzelpersonen. Ein Rundenwettkampf wird als
Mannschaft geschossen. Sportartneutral: eine Mannschaft ist eine benannte
Gruppe von Mitgliedern in einem Wettkampf, die Wertung bleibt `score_value`.

### 6.8 Plattform — zuletzt, bewusst

- Admin-Bereich: Vereine und Benutzer verwalten (heute nur lesend),
  `DELETE /club`-UI.
- Benutzerprofil-/Kontoseite.
- Geparkte Einstellungsseiten (Kontakt, Vorgaben, Gebühren, Zahlung).
- Public API + API-Keys, Webhooks, Passkeys/Apple OAuth/MFA.

Alles davon ist richtig und nichts davon fehlt einem Verein am Dienstagabend.

### Betrieb — klein, aber es beißt sonst wieder

- `COOKIE_DOMAIN` auf Prod (offen; ohne das ist der Login dort kaputt).
- Dev-Container prüft beim Start, ob `node_modules` bzw. `.venv` zur
  Abhängigkeitsdatei passen. Genau daran sind in dieser Session zwei Abende
  hängengeblieben — einmal `cmdk`, einmal `reportlab`.
- GitHub-Actions von Node-20-Actions wegbumpen, bevor die Runner es erzwingen.
- iOS: offiziell parken oder wiederbeleben — seit April unverändert, und jede
  Woche Schweigen macht die Entscheidung teurer.

## Nicht vergessen (Querschnitt, gilt in jeder Phase)

- Tests nach Pyramide, Regressionstest „rot gesehen" (Konvention).
- Ein pytest-Prozess gegen die geteilte `unefy_test`-DB.
- Zeitzonen: Server rechnet in der Vereins-Zeitzone.
- shadcn-Registry vor Eigenbau prüfen.
- i18n de+en für alles Neue, keine Quick-Look-Panels.
