# Plan: Rundmail

Stand 2026-08-12, Roadmap 6.4. Eine Nachricht an viele: an alle Mitglieder,
an eine Sparte, an ein Amt, an die Angemeldeten eines Termins, an die
Schuldner eines Jahres. Heute kann der Verein genau eine Sache verschicken —
einen Magic Link an eine Adresse.

## Abgrenzung, gleich am Anfang

**Pflichtmitteilung und Werbung sind nicht dasselbe.** Die Einladung zur
Mitgliederversammlung ist eine satzungsrechtliche Pflicht; der Newsletter über
das Sommerfest ist es nicht. Wer die Rundmail-Einwilligung verweigert hat, muss
die Einladung trotzdem bekommen — und die Sommerfest-Mail nicht. Eine
Absendemaske, die das nicht unterscheidet, zwingt den Vorstand jedes Mal zur
Wahl zwischen „rechtswidrig" und „unvollständig".

Deshalb trägt **jede Nachricht eine Art**:

| Art | Empfänger | Abmeldelink |
|---|---|---|
| `notice` (Pflichtmitteilung) | alle Aufgelösten, ohne Einwilligungsprüfung | nein |
| `newsletter` (Information/Werbung) | nur mit erteilter `newsletter`-Einwilligung | ja, verpflichtend |

Die Art ist eine Angabe des Absenders und keine Ableitung aus dem Text. Sie
steht im Formular über dem Betreff, mit einem Satz daneben, was sie bedeutet —
nicht versteckt in einem Klappmenü.

**Nicht in diesem Plan:** SMS und Push als Rundnachricht (Push gibt es, aber
als Ereignishinweis, nicht als Mitteilungskanal), Serienbriefe auf Papier,
Vorlagen mit Platzhaltern je Empfänger. Letzteres ist verlockend, weil 6.3 die
Maschinerie dafür hat — es ist trotzdem ein eigener Schritt, und ohne ihn
funktioniert die Rundmail.

## Leitplanken

1. **Der Versandweg bleibt SMTP.** Das Backend spricht bereits SMTP
   (`app/integrations/email.py`), jeder Self-Hoster hat einen Zugang, und
   Postmark, Brevo, SES und Mailjet bieten alle einen SMTP-Endpunkt an. Ein
   Versanddienst ist damit eine **Einstellung, keine Codeverzweigung** — dieselbe
   Entscheidung wie Volume vs. S3 bei der Ablage. Was ein Dienst zusätzlich
   kann, sind Bounces und Beschwerden, und die kommen als eigener, optionaler
   Schritt (s. u.), nicht als zweiter Versandweg.
2. **Wer die Mail bekommen hat, steht fest, sobald sie rausgeht.** Die
   Empfängerliste wird beim Absenden aufgelöst und als Zeilen eingefroren. Eine
   Liste, die man später neu auswertet, beantwortet eine andere Frage — „wer ist
   heute in der Sparte" statt „wer hat die Einladung bekommen".
3. **Ein Empfänger, eine Zeile, ein Zustand.** Versand ist nicht atomar: bei 200
   Adressen gehen 197 raus und drei prallen ab. Das muss sichtbar sein, statt
   hinter „gesendet" zu verschwinden.
4. **Nichts geht doppelt raus.** Jede Empfängerzeile wird genau einmal
   zugestellt; der Versandschleife darf ein Neustart nichts ausmachen.
5. **Abmelden ist so leicht wie Anmelden.** Jede `newsletter`-Mail trägt einen
   Abmeldelink, der ohne Anmeldung wirkt und die Einwilligung widerruft — über
   dieselbe Schreibweise, die „Meine Daten" benutzt. Dazu der
   `List-Unsubscribe`-Header, weil Mailprogramme danach suchen und ihr Fehlen
   ein Zustellbarkeitsproblem ist.
6. **Kein Anhang.** Eine angehängte Satzung macht aus 200 Mails 200 Kopien und
   kostet Zustellbarkeit. Seit der Ablage gibt es den besseren Weg: ein Link auf
   das Dokument, den nur sieht, wer angemeldet ist und darf.

## Datenmodell

### `email_messages` (`TenantModel + AuditMixin`)

| Feld | Typ | Bemerkung |
|---|---|---|
| `kind` | String: `notice` \| `newsletter` | s. o. |
| `subject` | String(255) | |
| `body` | Text | reiner Text, wie die übrigen Mails |
| `audience` | JSONB | die *Auswahl*, nicht das Ergebnis (s. u.) |
| `status` | String: `draft` \| `sending` \| `sent` \| `failed` | |
| `sent_by_user_id` | UUID? | |
| `queued_at` / `finished_at` | datetime? | |
| `recipient_count` | int | eingefroren beim Absenden |

### `email_recipients` (`TenantModel + TimestampMixin`)

| Feld | Typ | Bemerkung |
|---|---|---|
| `message_id` | UUID → email_messages, CASCADE | |
| `member_id` | UUID? → members, SET NULL | wer gemeint war |
| `email` | String(255) | die Adresse zum Zeitpunkt des Versands |
| `status` | String: `pending` \| `sent` \| `failed` \| `skipped` | |
| `error` | String(500)? | die Absage des Mailservers, gekürzt |
| `sent_at` | datetime? | |
| UniqueConstraint | (message_id, email) | dieselbe Adresse nie zweimal |

`skipped` ist ein eigener Zustand und nicht „failed": eine übersprungene
Adresse ist eine Entscheidung (keine Einwilligung, keine Adresse hinterlegt),
kein Fehler. Wer beides zusammenwirft, kann dem Vorstand nicht erklären, warum
40 von 300 nichts bekommen haben.

**Drei Gründe fürs Überspringen, nicht zwei**, weil 6.2 drei Zustände kennt:
`no_email` (keine Adresse hinterlegt), `refused` (widersprochen) und
`not_asked` (nie gefragt). Der Unterschied zwischen den letzten beiden ist die
einzige Zahl auf diesem Bildschirm, aus der ein Vorstand etwas machen kann:
„28 wurden nie gefragt" heißt *fragt sie*, „12 haben widersprochen" heißt
*lasst sie in Ruhe*. Zusammengezählt wäre beides nur „40 nicht erreicht".

### Die Auswahl (`audience`)

```json
{"type": "all"}
{"type": "function", "id": "…"}
{"type": "event", "id": "…", "include_waitlist": false}
{"type": "debtors", "year": 2026}
```

**„An eine Sparte" fehlt, und zwar aus einem Grund, der nicht in diesem Modul
liegt: es gibt keine Spartenmitgliedschaft.** Sparten existieren
(`divisions`), Anwesenheitseinheiten und Ämter zeigen darauf, der
Aufnahmeantrag fragt sogar danach — aber `applications.division_id` wandert bei
der Aufnahme nirgendwohin, und am Mitglied steht keine Sparte. Diese Auswahl
hier zu erfinden hieße, die Mitgliedschaft in einer Sparte nebenbei im
Mailmodul zu definieren. Sie kommt als eigene Änderung (Mitglied ↔ Sparte,
inklusive Übernahme aus dem Antrag) und ist danach *eine weitere Zeile* in
dieser Aufzählung — die Form der Auswahl ist genau dafür gebaut.

Gespeichert wird die Auswahl, verschickt wird die aufgelöste Liste. Die
Auflösung ist eine reine Funktion über die vorhandenen Repositories und lässt
sich damit einzeln testen — sie ist der Teil, der still falsch sein kann.

## Der Schalter davor

Seit 2026-08-12 hat das Backend `EMAIL_DELIVERY` (`auth_only` als Standard,
dazu `all` und `none`) mit `EMAIL_ALLOWLIST`. Eine Installation hält also
standardmäßig alles zurück außer Anmeldelink und Anmeldecode — genau deshalb,
weil sie echte Mitgliedsadressen zum Testen enthält, lange bevor jemand sie
anschreiben will.

**Für die Rundmail heißt das zweierlei.** Erstens: eine zurückgehaltene
Adresse ist kein Fehler, sondern bekommt `skipped` mit dem Grund `held_back` —
derselbe Zustand wie „keine Einwilligung", weil in beiden Fällen eine
Entscheidung der Installation greift und nicht ein Mailserver streikt.
Zweitens: das Verfassen-Formular muss es sagen. Ein Vorstand, der „an 143
gesendet" liest, während drei davon rausgingen, glaubt eine Zahl, die nicht
stimmt. Steht der Schalter nicht auf `all`, gehört ein Hinweis über den
Absende-Knopf.

## Versand

Eine Schleife im Lifespan, in der Bauform von `app/tasks/retention.py`:
Redis-`SET NX` als Sperre, ein Paket pro Runde, idempotent je Empfängerzeile.

- Kein ARQ. Das Backend hat keinen Job-Runner, und ein Verein soll für eine
  Rundmail keinen zweiten Prozess deployen müssen.
- **Pakete**, weil ein Mailserver bei 300 Verbindungen in zehn Sekunden dicht
  macht: `EMAIL_BATCH_SIZE` je Runde, `EMAIL_SEND_INTERVAL_SECONDS` dazwischen.
- **Ein Fehler ist ein Fehler dieser Zeile.** Der Rest läuft weiter; die Zeile
  wird mit `error` markiert und später erneut versucht, begrenzt oft.
- **Neustart-fest**: `pending` bleibt `pending`, `sent` wird nie noch einmal
  angefasst. Eine Nachricht, die halb raus ist, macht nach dem Neustart dort
  weiter, wo sie stand.

Neue Einstellungen:

| Einstellung | Standard | Zweck |
|---|---|---|
| `EMAIL_BATCH_SIZE` | 25 | Adressen je Runde |
| `EMAIL_SEND_INTERVAL_SECONDS` | 10 | Pause zwischen Paketen |
| `EMAIL_MAX_ATTEMPTS` | 3 | dann `failed` |
| `EMAIL_MAX_RECIPIENTS` | 1000 | je Nachricht, gegen den Fehlgriff |

## API

Alles unter `/api/v1/messages/…`, schreiben nur `board` und aufwärts.

| Endpunkt | Bemerkung |
|---|---|
| `POST /preview` | löst die Auswahl auf und zählt: „geht an 143, übersprungen 12" — **vor** dem Absenden |
| `POST /` | anlegen und in die Warteschlange stellen |
| `POST /{id}/test` | dieselbe Mail an die eigene Adresse, ohne Empfängerzeilen |
| `GET /` | Historie, paginiert |
| `GET /{id}` | eine Nachricht mit Zählern |
| `GET /{id}/recipients` | Zeilen mit Zustand, gefiltert nach `failed`/`skipped` |

Der Abmeldelink liegt außerhalb von `/api/v1`, wie `join` und `verify`:
`GET /unsubscribe/{token}` zeigt eine Seite, `POST` widerruft. Ein
GET-Aufruf darf nicht widerrufen — Mailprogramme laden Links vor.

## Web

- Navigation: **„Nachrichten"** in der Gruppe *Vereinsleben*, nur Vorstand.
- Liste der verschickten Nachrichten über die geteilte Data-Table: Betreff,
  Art, Datum, „143 / 12 / 3" (zugestellt / übersprungen / fehlgeschlagen).
- Verfassen: Art, Betreff, Text, Empfängerauswahl mit **Zählung im Formular**,
  Testversand, dann Absenden mit Bestätigung, die die Zahl nennt.
- Detailseite mit den Empfängerzeilen, filterbar auf das, was schiefging.
- i18n de+en von Anfang an.

## Phasen

**Phase 0 — Auflösung.** Die Empfängerauflösung als reine, getestete Funktion:
fünf Auswahlarten, Einwilligungsfilter je Nachrichtenart, Mitglieder ohne
Adresse als `skipped`. Kein Versand, kein UI.

**Phase 1 — Modell, Warteschlange, API. Fertig 2026-08-12.** Migration
`a71c3f5e8d24`, `email_messages` + `email_recipients`, Versandschleife im
Lifespan, `/api/v1/messages/…`, Abmeldelink unter `/unsubscribe/{token}`,
30 Tests.

Vier Dinge, die unterwegs entschieden wurden:

- **Eine Adresse wird nie zweimal beliefert, beide Mitglieder bleiben im
  Protokoll.** Das Ehepaar mit einem Postfach bekommt eine Einladung; das
  zweite Mitglied steht als `skipped`/`duplicate` in der Liste. Möglich über
  einen *partiellen* Unique-Index (`WHERE status <> 'skipped'`) — die Zusage
  lautet „keine Adresse doppelt beliefert", nicht „kein Mitglied doppelt
  aufgeführt".
- **Abmelde-Token abgeleitet statt gespeichert**: Mitglieds-ID plus
  HMAC über `SESSION_SECRET`. Kein Ablauf (die Mail liegt Jahre im Postfach),
  keine Tabelle, die mit jedem Versand wächst. Preis: eine Rotation des
  Secrets entwertet alle je verschickten Links — dokumentiert in
  `app/core/unsubscribe.py`.
- **`List-Unsubscribe` samt One-Click**, weil ohne den Header der
  Abmeldeknopf in Gmail und Outlook verschwindet und die Leute stattdessen
  „Spam" drücken. Der Header zeigt aufs Backend (Maschine), der Link im Text
  auf die Weboberfläche (Mensch).
- **Der Drosselschalter gilt auch mitten im Versand.** Wer `EMAIL_DELIVERY`
  umlegt, während eine Rundmail läuft, stoppt den Rest: die verbleibenden
  Zeilen werden `skipped`/`held_back`, nicht `sent`. Beim Einstellen wird mit
  eigenem Code `EMAIL_HELD_BACK` abgelehnt — „erreicht niemanden" hätte den
  Vorstand in die Einwilligungen geschickt statt in die Einstellungen.

**Phase 2 — Web.** Liste, Verfassen mit Vorschau und Testversand, Detailseite.

**Phase 3 — Feinschliff.** Erneut versuchen für fehlgeschlagene Zeilen,
Bounce-Verarbeitung als optionaler Webhook, Platzhalter je Empfänger.

## Tests

Nach der Pyramide, ein pytest-Prozess. Tragend, also jeweils rot gesehen:

- **Mandantentrennung**: die Auflösung liefert nie eine Adresse aus Verein B.
- **Einwilligung wirkt**: ein Mitglied ohne `newsletter`-Einwilligung steht bei
  `newsletter` als `skipped` in der Liste — und bei `notice` als `pending`.
- **Nie gefragt ≠ abgelehnt**: wer nie gefragt wurde, bekommt keinen
  Newsletter, und das Ergebnis unterscheidet ihn von einer Verweigerung.
- **Kein Doppelversand**: zwei Läufe der Schleife über dieselbe Nachricht
  verschicken jede Adresse einmal.
- **Neustart mittendrin**: nach einem Abbruch gehen die restlichen Zeilen
  raus und keine der bereits gesendeten noch einmal.
- **Ein Fehler bleibt lokal**: eine abgelehnte Adresse hält die anderen nicht
  auf und landet als `failed` mit Grund.
- **Abmelden wirkt**: nach dem Abmeldelink steht die Einwilligung auf
  widerrufen, und die nächste Auflösung überspringt die Adresse.
- **Kein Widerruf per GET**.

## Zu entscheiden

1. **Versandweg** — Empfehlung: SMTP bleibt der einzige Weg im Code, ein
   Dienst ist eine Einstellung. Kostet keine Abhängigkeit und keine zweite
   Codebahn.
2. **Art je Nachricht** (`notice` / `newsletter`) statt einer globalen
   Einstellung — Empfehlung wie oben beschrieben.
3. **Absenderadresse**: heute eine je Installation (`SMTP_FROM`). Ein Verein
   will „vorstand@verein.de" als Antwortadresse. Vorschlag: `Reply-To` je
   Verein aus den Vereinsdaten, `From` bleibt die der Installation — alles
   andere bricht SPF/DKIM und landet im Spam.
