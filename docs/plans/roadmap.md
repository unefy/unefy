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

### 6.1 Digitaler Mitgliedsantrag ✓ (2026-08-10)

Vorher legte ein Vorstandsmitglied neue Mitglieder von Hand an — der Beitritt
selbst fand außerhalb des Systems statt, auf Papier oder per Mail.

Gebaut:

- Öffentliches Formular unter `/join/{slug}`, ohne Anmeldung erreichbar.
- Es erzeugt einen **Antrag**, kein Mitglied. Aufnahme ist ein Beschluss, und
  ein Formular fasst keine Beschlüsse: der Vorstand nimmt an oder lehnt ab,
  und erst die Annahme legt den Mitgliedsdatensatz an — samt Mitgliedsnummer,
  Beitragszuordnung und Mandatsreferenz.
- Beitragsart und Sparte wählbar, soweit der Verein sie anbietet. Was der
  Verein nicht anbietet, wird abgewiesen statt als unerfüllbarer Wunsch
  gespeichert.
- SEPA-Mandat gleich mit erteilen. Die Referenz entsteht erst bei der Annahme
  — vorher gibt es keine Mitgliedschaft, die sie benennen könnte.
- **Pro Verein abschaltbar, und aus by default.** Das ist der einzige
  Endpunkt, durch den ein Unangemeldeter schreibt; ihn per Migration für alle
  bestehenden Vereine zu öffnen wäre eine Entscheidung gewesen, die kein
  Verein getroffen hat. Schalter in den Vereinseinstellungen.
- Missbrauchsschutz: Rate-Limit wie bei den Auth-Endpunkten (5 Anträge pro
  5 Minuten), und die Antwort ist für Mitglieder und Fremde identisch — sonst
  wäre das Formular eine Mitgliederauskunft mit Zwischenschritt.
- Einwilligungen (Foto, Rundmail, Verzeichnis) werden im selben Formular
  erhoben, getrennt vom Datenschutzhinweis: eine Einwilligung, die an eine
  Voraussetzung gekoppelt ist, ist nicht freiwillig. Sie liegen am Antrag und
  wandern in 6.2 an das Mitglied.

Offen und bewusst so:

- Die gewünschte Sparte wird bei der Annahme **nicht** übernommen — Mitglieder
  sind heute nicht mit Sparten verknüpft (nur Anwesenheit und Ämter). Sie
  bleibt am Antrag stehen, der Vorstand liest sie dort.
- Abgelehnte und offene Anträge unterliegen einer eigenen Frist — sie sind
  Bewerberdaten, keine Mitgliederdaten. Gehört zu 6.2.
- Der Antragsteller wird nicht automatisch benachrichtigt. Eine Absage, die
  als Serienmail ankommt, ist schlechter als ein Anruf.

### 6.2 Einwilligungen und Auskunft (DSGVO) — teilweise (2026-08-11)

Gehört unmittelbar zu 6.1: Der Antrag ist der Moment, in dem eingewilligt
wird, und der einzige, in dem es unaufwendig ist.

**Gebaut:**

- **Einwilligungen je Mitglied** — Foto, Rundmail, Verzeichnis — als
  **fortgeschriebenes Verzeichnis, nicht als drei Häkchen am Mitglied.** Eine
  Einwilligung muss beweisbar sein und ein Widerruf so leicht wie die
  Erteilung; beides überlebt keine Spalte, die überschrieben wird. Es wird nur
  angehängt, nie geändert oder gelöscht.
- **Drei Zustände, nicht zwei**: erteilt, verweigert, und *nie gefragt*. Das
  Fehlen einer Antwort ist keine Ablehnung, und die beiden zusammenfallen zu
  lassen würde genau die Unterscheidung löschen, auf die es ankommt.
- **Die Einwilligung wirkt.** Wer die Nennung im Verzeichnis verweigert,
  erscheint dort nicht mehr — sonst wäre sie Dekoration: erfragt, gespeichert,
  ignoriert. Wer nie gefragt wurde, bleibt drin; die Vereinsliste steht nicht
  allein auf Einwilligung, und ein unbeantwortetes Feld darf kein Verzeichnis
  leeren.
- **Übernahme aus dem Antrag** bei der Aufnahme, gestempelt mit dem Zeitpunkt
  des Formulars statt dem der Entscheidung. Verweigerungen wandern mit.
- **Selbstbedienung** unter „Mein Bereich ▸ Meine Daten": erteilen und
  widerrufen mit demselben Aufruf. Das Mitglied kann nicht rückdatieren, der
  Vorstand schon — ein Papierformular wurde unterschrieben, als es
  unterschrieben wurde.
- **Auskunft nach Art. 15** als JSON-Bündel: Stammdaten, Einwilligungen,
  Verbände, Ämter, Beiträge, Sollstellungen, Anwesenheit, Anmeldungen.
  Selbstbedienung ohne Umweg über den Vorstand, und für Anfragen auf Papier
  zusätzlich am Mitglied.

**Offen:**

- **Löschung nach Art. 17** im Verhältnis zu den Aufbewahrungsfristen, die pro
  Verein bereits konfigurierbar sind. Heute ist Löschen ein Soft-Delete — für
  ein Löschersuchen zu wenig. Das ist der aufwendige Teil: Was gelöscht werden
  muss, was anonymisiert werden darf und was zehn Jahre bleiben *muss*
  (Steuer- und Handelsrecht), lässt sich nicht in einem Rutsch entscheiden.
- **Eigene Frist für Bewerberdaten** aus 6.1 — abgelehnte und offene Anträge
  sind keine Mitgliederdaten.

Nicht baubar, und das gehört im Produkt auch so benannt: Datenschutzerklärung,
Verarbeitungsverzeichnis und Auftragsverarbeitungsverträge sind Vereinstext.
Ein Gerüst mit Platzhaltern können wir liefern, Rechtsberatung nicht.

### 6.3 Mitgliedsbescheinigungen ✓ (2026-08-11)

Zwei Sorten Dokument, und der Unterschied entschied die Bauform:

- **Vorgeschriebene Formen** (Zuwendungsbestätigung nach amtlichem Muster, die
  §14-Bescheinigung) bleiben fest gebaut. Ein Editor wäre dort eine Einladung,
  ein ungültiges Dokument zu erzeugen.
- **Freie Formen** laufen über **Textvorlagen mit Variablen** — kein
  Layout-Editor, entschieden am 2026-08-10.

**Gebaut:**

- Vorlagen unter *Einstellungen ▸ Bescheinigungen*: Name, Überschrift und
  fließender Text, den der Verein selbst zusammenstellt. Leerzeilen trennen
  Absätze, sonst ist nichts an dem Text Auszeichnung.
- **Ein Satz Platzhalter, an einer Stelle definiert** (`app/services/
  document_variables.py`). Er speist die Vervollständigung, die Prüfung beim
  Speichern und das Einsetzen beim Ausstellen. Eine zweite Liste wäre eine
  zweite Gelegenheit, der ersten zu widersprechen. Fünfzehn Namen von
  `{{mitglied.name}}` bis `{{jahr}}`; das Muster ist eng gefasst, damit eine
  geschweifte Klammer im Fließtext nicht halb erkannt wird.
- **Autovervollständigung**: `{{` öffnet die gefilterte Liste, Pfeiltasten und
  Enter fügen ein, die Schreibmarke landet hinter dem Eingefügten. Daneben
  steht der ganze Satz zum Anklicken.
- **Ein unbekannter Platzhalter wird beim Speichern abgelehnt**, und alle auf
  einmal genannt — jemandem einen Tippfehler nach dem anderen zu melden ist
  keine Art, einen Brief zu bearbeiten. Die Vorschau rendert gegen
  offensichtlich erfundene Beispieldaten, nie gegen ein echtes Mitglied.
- **Das Ausstellen friert den gerenderten Text ein.** Eine Vorlage ändert sich
  — dafür ist sie da — und ein Nachdruck oder eine Prüfung Monate später muss
  zeigen, was der Empfänger bekommen hat, nicht was die Vorlage heute sagt.
  Wird eine Vorlage gelöscht, bleiben die daraus ausgestellten Dokumente
  vollständig bestehen.
- **Widerruf statt Korrektur**: ein Fehler wird widerrufen und neu
  ausgestellt. Der Empfänger hält das falsche Papier weiterhin in der Hand,
  und die Spur muss zeigen, dass es das gab. Das PDF eines widerrufenen
  Dokuments sagt das auf seiner Vorderseite, nicht nur auf der Prüfseite.
- **Prüfbar mit QR und Prüfcode**, je Vorlage abschaltbar. Die `/verify`-Seite
  trägt jetzt beides — §14-Nachweis und Vereinsbescheinigung; wer den QR
  scannt, hält ein Blatt Papier und weiß nicht, aus welcher Tabelle es kommt.
  Sie nennt Titel, Verein, abgekürzten Namen und Datum, **nie den Text**: wer
  bloß einen Code gefunden hat, soll erfahren, dass das Dokument echt ist, und
  sonst nichts.
- Briefkopf und Fußzeile kommen aus den Vereinseinstellungen, je Vorlage
  abschaltbar.

**Mustervorlagen (2026-08-11):** fünf gängige Vereinsdokumente stehen als
Entwurf bereit — Mitgliedsbescheinigung, dieselbe mit Beitragsangabe,
Austrittsbestätigung, Bescheinigung über ehrenamtliche Tätigkeit und die
Urkunde für langjährige Mitgliedschaft. Jedes trägt einen Hinweis, was der
Verein daran prüfen muss, und **nichts wird von allein angelegt**: ein Klick
öffnet den Editor mit dem Text, gespeichert wird erst nach dem Lesen. Ein Test
hält die Muster gegen den Platzhaltersatz — eine ausgelieferte Vorlage, die
sich nicht speichern lässt, wäre schlimmer als gar keine.

Die **Zuwendungsbestätigung ist keine Vorlage** — sie folgt einem amtlichen
Muster und ist deshalb **fest gebaut** (siehe unten). Sie als freien Text
nachzubauen wäre genau die Einladung, ein ungültiges Dokument zu erzeugen.
Ebenso fehlt eine Beitragsbescheinigung über die Zahlungen eines Jahres: dafür
müsste beim Ausstellen ein Jahr gewählt werden, und dieses Feature kennt keine
Eingabe je Ausstellung. Lieber keine als eine, die stillschweigend den
falschen Zeitraum meldet.

Dafür sind vier Platzhalter dazugekommen — Beitrag, Beitragsart, laufende
Ämter und volle Mitgliedsjahre. Beitrag und Ämter werden **zum Stichtag**
aufgelöst, nicht als neueste Zeile: eine Bescheinigung, die den erst zur
nächsten Saison eingetragenen Beitrag nennt, ist am Tag der Übergabe falsch.

**Zuwendungsbestätigung (2026-08-11):** eigenes, fest gebautes Dokument nach
dem amtlichen Muster — Aussteller, Zuwendender, Betrag in Ziffern **und**
Buchstaben, Tag und Art der Zuwendung, Verzicht auf Aufwendungsersatz, der
Anerkennungssatz mit Finanzamt, Steuernummer und Bescheiddatum, die
Verwendungsbestätigung und der Haftungshinweis nach § 10b Abs. 4 EStG. Die
vorgeschriebenen Sätze stehen gesammelt in `TEXTS`, damit ein Abgleich mit dem
aktuellen amtlichen Muster eine offensichtliche Änderung an einer Stelle ist.

Zwei Verweigerungen tragen das Ganze:

- **Mitgliedsbeiträge sind bei Sportvereinen nicht abziehbar** (§ 10b Abs. 1
  Satz 8 EStG i. V. m. § 52 Abs. 2 Nr. 21 AO). Wer sie trotzdem bescheinigt,
  gibt dem Mitglied ein Papier, das das Finanzamt zurückweist, und haftet für
  die verkürzte Steuer. Der Verein muss deshalb ausdrücklich erklären, dass
  seine anerkannten Zwecke das zulassen — Vorgabe ist *nein*, und das Formular
  bietet die Art dann gar nicht erst an.
- **Unvollständige Steuerdaten sperren das Ausstellen.** Eine Bestätigung, die
  amtlich aussieht und nichts behauptet, ist schlimmer als keine. Die Seite
  sagt vorher, was fehlt, statt hinterher.

Der Vereinsstand wird in jede Bestätigung kopiert, nicht referenziert: eine
Bestätigung von 2024 muss weiterhin sagen, was 2024 galt. Ein Fehler wird
widerrufen und neu ausgestellt — der Empfänger hat das Papier bereits, und das
Finanzamt hat es womöglich gesehen. Der Betrag in Worten hat ein eigenes Modul
mit eigenen Tests: eine Ziffer lässt sich mit einem Stift ändern, ein Wort
nicht.

**Vor dem Produktivbetrieb gegen das aktuelle amtliche Muster prüfen.** Der
Aufbau folgt ihm, aber ob jeder Satz wörtlich dem heute geltenden Stand
entspricht, ist eine Frage an den Steuerberater des Vereins und nicht an uns.

**Ein Aussehen für alle drei (2026-08-11):** §14-Nachweis,
Zuwendungsbestätigung und freies Dokument trugen je eigene Ränder, Größen und
Grauwerte — so werden aus drei Dokumenten eines Vereins drei Dokumente von drei
Vereinen. `app/services/pdf_theme.py` besitzt diese Entscheidungen jetzt
einmal: kleiner gesperrter Briefkopf, eine große Überschrift, Haarlinien statt
Kästen, Angaben als Wert unter der Beschriftung. Einfarbig, weil die App es ist
— eine Farbe, die das Produkt nie verwendet, liest sich wie von woanders.

Die PDFs **öffnen sich im Browser**, statt im Download-Ordner zu landen: was
gerade ausgestellt wurde, will man zuerst lesen. Auskunftsdatei, SEPA-XML und
Standbuch bleiben Downloads — das sind Daten, keine Schriftstücke.

**Offen:**

- **Keine eingebettete Schrift.** Die base-14-Helvetica hält die Datei klein
  und den Build ohne Binärdatei, aber sie ist nicht in der PDF enthalten:
  Betrachter ohne echte Helvetica setzen eine breitere Schrift ein, und der
  Umbruch stimmt dann nicht mehr — auf diesem Rechner läuft die Haftungszeile
  in poppler über den Rand, in Chrome nicht. Für ein Papier, das ein Verein
  ausdruckt und weitergibt, ist das irgendwann eine eigene Entscheidung wert.
- Das Logo bleibt draußen. `logo_url` zeigt irgendwohin, und es beim Rendern zu
  holen hieße eine blockierende Anfrage an eine URL, die der Verein bestimmt —
  im besten Fall langsam, im schlechtesten eine SSRF. Braucht erst die
  Dateiablage aus 6.6.
- Vereinfachter Zuwendungsnachweis bis 300 € (Bareinzahlungsbeleg /
  Buchungsbestätigung) — braucht kein Dokument von uns, aber ein Hinweis im
  Produkt wäre freundlich.

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
