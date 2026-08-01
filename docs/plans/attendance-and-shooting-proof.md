# Plan: Anwesenheit (Kern) und Schießnachweis (Modul)

Anwesenheitserfassung als Kernfunktion, darauf aufbauend der §14-Nachweis im
Schießsport-Modul. Anlass: Der Schießnachweis ist der Anwendungsfall mit dem
schärfsten Beweisanspruch — er setzt die Latte, die Funktion selbst brauchen
aber alle Vereine (Training, Jugendarbeit, Beschlussfähigkeit).

## Abgestimmte Entscheidungen

| Frage | Entscheidung |
|---|---|
| Einordnung | Anwesenheit gehört in den **Kern**, nicht ins Schießsport-Modul. |
| Standardverfahren | Aufsicht hakt ab (`manual`). Das ist der heutige Papierstand und bleibt vollwertig. |
| Ausbaustufe | Rotierender QR auf dem Mitgliedsgerät, von der Aufsicht gescannt. |
| NFC | **Nicht im Scope.** Weder Wandtags noch Mitgliedskarten noch Phone-to-Phone. |
| Beweisführung | Stufe 0 (Audit + Freeze) und Stufe 1 (Hash-Kette + Zeitstempel). |
| Qualifiziertes Siegel | Stufe 2, bewusst zurückgestellt. Felder werden vorbereitet. |
| Aufbewahrung | Nachweisdaten jahrelang, Gerätekontext wenige Wochen. Getrennte Tabellen. |
| Bescheinigung | Wird von einem Menschen ausgestellt, nie automatisch. |

### Warum kein NFC

Phone-to-Phone ist plattformseitig nicht symmetrisch verfügbar. Android beherrscht
Host Card Emulation frei, das iPhone kann als Leser dienen, aber als Karte nur mit
gesondertem Apple-Entitlement und beschränkt auf definierte Anwendungsfälle. Für ein
Projekt, das jeder selbst hosten können soll, ist das ein Ausschlusskriterium — man
müsste für iPhone-Mitglieder ohnehin einen zweiten Weg bauen. Dann ist dieser zweite
Weg der einzige. Mitgliedskarten mit NTAG 424 DNA bleiben als spätere Option
interessant, weil sie ohne Smartphone funktionieren, sind aber hier nicht Scope.

## Leitprinzipien

1. **Jeder Check-in beweist zwei Dinge:** *wer* (Person) und *wo/wann* (Ort). Die
   Verfahren unterscheiden sich nur darin, welche Seite technisch abgesichert ist.
2. **Beweiskraft ist eine Spalte, keine Produktentscheidung.** `assurance` erlaubt
   dem Schießsport-Modul, ein Mindestniveau zu verlangen, während ein
   Tischtennisverein weiter Kästchen abhakt. Ein Codepfad, kein Zweig.
3. **Der Beweis liegt in der Datenspur, nicht im PDF.** Im Zweifel lautet die Frage
   nie „ist die Unterschrift echt", sondern „woher wisst ihr das". Darauf antwortet
   der Audit-Trail.
4. **Nachweis konservieren, Rohdaten verfallen lassen.** Was den Check-in belegt,
   bleibt jahrelang. Was ihn technisch begleitet hat, verfällt nach Wochen — als
   Fingerabdruck und Prüfergebnis, nicht als Rohdatum.
5. **Kein Automatismus bei der Bescheinigung.** Die Auswertung schlägt vor, ein
   Vorstandsmitglied stellt aus. Sauberer im Verein und außerhalb von Art. 22 DSGVO.

## Verfahren

| Methode | Person bewiesen durch | Ort bewiesen durch | `assurance` |
|---|---|---|---|
| `manual` | Behauptung der Aufsicht | Behauptung der Aufsicht | `low` |
| `staff_scan` | rotierender Code vom Mitgliedsgerät | das autorisierte Scan-Gerät vor Ort | `high` |

Weitere Methoden (`venue_scan`, `self`, `nfc_tap`) sind im Modell vorgesehen, aber
nicht implementiert. Sie werden validiert abgelehnt, bis sie gebaut sind.

### Rotierender Mitglieds-QR

Die App holt einen **Seed** mit 24 Stunden Gültigkeit und rechnet daraus offline alle
30 Sekunden einen Code. Offline-Fähigkeit ist keine Kür: Schießstände liegen oft im
Keller ohne Empfang.

```
uf1.<member_ref>.<counter>.<hmac>

  member_ref = tenantweites Pseudonym des Mitglieds
               (ein abfotografierter Code leakt keine Member-ID)
  counter    = floor(unix_time / 30)
  hmac       = HMAC-SHA256(seed, tenant || member || counter), 10 Byte, Base32
```

Prüfung im Backend:

- HMAC über ein Fenster von ±1 Counter (Uhrendrift).
- Seeds aus den letzten 48 Stunden werden akzeptiert (Kulanz bei fehlender Verbindung).
- Einmalverbrauch über Redis: `checkin:{tenant}:{member}:{counter}`, TTL 90 s.
  Damit ist Screenshot-Replay tot.
- Das Scan-Gerät darf offline puffern. `checked_in_at` (Gerätezeit) und `synced_at`
  werden getrennt gespeichert; eine Session akzeptiert Nachträge bis zu ihrem
  Abschluss, danach nicht mehr.

## Datenmodell

### Kern — `app/models/attendance.py`

```python
class AttendanceSession(Base, AuditMixin, TenantMixin, SoftDeleteMixin):
    """Zeitfenster, in dem an einem Ort eingecheckt werden kann."""
    __tablename__ = "attendance_sessions"

    title: str
    division_id: FK divisions SET NULL | None
    event_id: FK events SET NULL | None      # optional an den Kalender gehängt
    location: str | None
    opens_at / closes_at: datetime
    status: "open" | "closed"
    supervisor_member_id: FK members | None  # Standaufsicht
    closed_at: datetime | None
    closed_by: uuid | None
    close_hash: str | None                   # Stufe 1, siehe Beweisführung
```

Bewusst nicht direkt an `Event` gehängt: Schießbetrieb findet jeden Dienstag statt,
ohne dass jemand dafür Kalendereinträge pflegt — und `Event` kennt noch keine
Wiederholung. Die Verknüpfung bleibt optional.

```python
class AttendanceRecord(Base, AuditMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "session_id", "member_id"),
        Index("ix_attendance_tenant_member_date", "tenant_id", "member_id", "occurred_on"),
    )

    session_id: FK attendance_sessions CASCADE
    member_id:  FK members
    occurred_on: date                  # denormalisiert, trägt die 12-Monats-Auswertung
    checked_in_at: datetime
    checked_out_at: datetime | None
    synced_at: datetime | None
    method:    "manual" | "staff_scan" | ...
    assurance: "low" | "medium" | "high"
    verified_by_user_id: uuid | None   # Pflicht bei manual und staff_scan
    note: str | None

    # Überlebt den Kontext (siehe Aufbewahrung)
    context_digest: str | None         # SHA-256 über die Kontextzeile
    context_verdict: str | None        # "ok" | "suspicious" | "unchecked"
```

```python
class AttendanceCheckinContext(Base, TimestampMixin, TenantMixin):
    """Technischer Kontext eines Check-ins. Kurze Frist, eigener Löschjob."""
    __tablename__ = "attendance_checkin_contexts"

    attendance_record_id: FK attendance_records CASCADE, unique
    install_id: str | None        # stabile ID pro App-Installation
    staff_device_id: str | None   # scannendes Gerät
    code_counter: int | None
    user_agent: str | None
    expires_at: datetime          # der Löschjob fährt hierüber
```

`install_id` statt Gerätefingerabdruck ist Absicht: Das Handymodell ist als
Betrugssignal fast wertlos (es gibt Zehntausende iPhone 15). Das reale Muster ist
„ein Gerät checkt an einem Abend zwölf verschiedene Mitglieder ein", und dafür ist
die Installations-ID das treffende Signal — bei gleichzeitig geringerer
Personenbeziehbarkeit.

### Schießsport-Modul

```python
class ShootingRecordDetail(Base, AuditMixin, TenantMixin):
    """1:1-Erweiterung eines AttendanceRecord."""
    attendance_record_id: FK attendance_records CASCADE, unique
    club_discipline_id: FK club_disciplines SET NULL | None
    weapon_category: "kurzwaffe" | "langwaffe" | "luftdruck" | None
    rounds_fired: int | None
```

Waffenkategorie als typisierte Spalte statt JSONB — anders als
`competitions.sport_data`, weil die §14-Auswertung genau danach filtert und der
Filter indizierbar sein muss.

```python
class ShootingProofCertificate(Base, AuditMixin, TenantMixin):
    """Die ausgestellte Bescheinigung. Eingefroren zum Ausstellungszeitpunkt."""
    member_id: FK members
    period_start / period_end: date
    session_count / months_covered: int
    rule_key: str                  # welche Schwelle galt
    result: "passed" | "failed"
    issued_at: datetime
    issued_by_user_id: uuid
    revoked_at / revoked_by / revoke_reason

    record_ids: JSONB              # welche Datensätze ausgewertet wurden
    content_hash: str              # SHA-256 über kanonisches JSON
    verification_code: str, unique # kurz, undurchratbar, für den QR
    document_ref: str | None       # PDF im Storage
    seal: bytes | None             # Stufe 2, vorerst leer
```

## Aufbewahrung

Das zentrale Spannungsfeld: Der Nachweis soll über Jahre belastbar bleiben, die
begleitenden Gerätedaten unterliegen der Datenminimierung. Auflösung über **zwei
Geschwindigkeiten**.

| | Nachweisschicht | Kontextschicht |
|---|---|---|
| Tabelle | `attendance_records` | `attendance_checkin_contexts` |
| Rechtsgrundlage | Art. 6 I c/f DSGVO i. V. m. WaffG | Art. 6 I f, berechtigtes Interesse |
| Inhalt | Mitglied, Datum, Methode, Beweiskraft, wer bestätigt hat | Installations-ID, Scan-Gerät, Counter |
| Frist | `tenants.attendance_retention_years`, Default 10 | `tenants.attendance_context_retention_days`, Default 90 |
| Löschung | nur durch Retention-Job nach Ablauf | eigener Job über `expires_at` |

**Der Kniff:** Beim Anlegen des Kontexts wird sofort `context_digest` (Hash über die
Kontextzeile) und nach der Missbrauchsprüfung `context_verdict` auf dem
*Anwesenheitsdatensatz* gesetzt. Läuft die Kontextzeile ab, verschwinden die
Rohdaten — belegbar bleibt über Jahre: „zu diesem Check-in existierte ein technischer
Kontext mit diesem Fingerabdruck, er wurde geprüft und war unauffällig." Das ist
genau die Aussage, die im Zweifel gebraucht wird, ohne die Verhaltensspur zu
konservieren.

Weitere Regeln:

- **Kein Hard-Delete** auf `attendance_records` außerhalb des Retention-Jobs.
  Korrekturen laufen über `SoftDeleteMixin` plus Audit-Eintrag mit Begründung.
- Ein Löschverlangen nach Art. 17 greift für die Nachweisschicht nicht, solange die
  Aufbewahrungspflicht läuft (Art. 17 III b). Das ist eine Verteidigung, kein Problem —
  muss aber im Verarbeitungsverzeichnis stehen und dem Mitglied begründet werden.
- **Zweckbindung:** Anwesenheitsdaten dürfen nicht in Beitragsberechnung oder
  Aktivitätsranglisten wandern. Kein Join aus dem Beitragsmodul heraus.

## Beweisführung

### Stufe 0 — Audit und Einfrieren

Kostet nichts, ist später kaum nachrüstbar, adressiert den realistischen Angriff
(nachträgliche Gefälligkeitseinträge):

- Jede Korrektur und jede Löschung eines Anwesenheitsdatensatzes erzeugt einen
  Eintrag über das vorhandene [`models/audit.py`](../../backend/app/models/audit.py)
  mit Benutzer, Zeitpunkt, Vorher/Nachher und Begründung. Ein nachträglich
  eingefügter Termin muss als nachträglich eingefügt erkennbar sein.
- Beim Ausstellen einer Bescheinigung werden `record_ids` und `content_hash`
  festgeschrieben. Damit ist später beweisbar, dass genau dieses PDF zu genau diesen
  Datensätzen gehört, auch wenn einer davon danach korrigiert wurde.
- Die Bescheinigung wird von einem Menschen ausgestellt, die Auswertung schlägt nur vor.

### Stufe 1 — Hash-Kette und externer Zeitstempel

```python
class ProofChainEntry(Base, TimestampMixin, TenantMixin):
    """Append-only. Jeder Eintrag kettet sich an den vorherigen."""
    seq: int                                  # fortlaufend je Tenant
    entry_type: "session_close" | "certificate"
    subject_id: uuid                          # Session bzw. Bescheinigung
    content_hash: str
    prev_hash: str
    chain_hash: str                           # H(prev_hash || content_hash)

class ProofChainAnchor(Base, TimestampMixin, TenantMixin):
    """Kettenkopf, extern zeitgestempelt."""
    seq_to: int
    chain_hash: str
    tsa_token: bytes                          # RFC 3161
    anchored_at: datetime
```

- Beim **Abschluss einer Session** wird über deren Datensätze gehasht und ein
  Kettenglied angehängt (`close_hash` auf der Session). Danach sind Nachträge in diese
  Session ausgeschlossen — Backdating wird erkennbar.
- Beim **Ausstellen einer Bescheinigung** ebenso.
- Ein Job stempelt den Kettenkopf regelmäßig (täglich oder monatlich) bei einem
  externen RFC-3161-Dienst.

Der externe Zeitstempel ist die einzige Maßnahme, die auch im **Self-Hosted-Betrieb**
trägt. Dort kontrolliert der Verein den Server, womit jedes „wir können nicht
manipulieren" sonst zusammenfällt. Der Anker liegt außerhalb dieses Zugriffs.

### Prüfcode auf dem PDF

Der QR schützt gegen Fälschung durch Dritte — der wahrscheinlichere Angriff ist ein
in Word gebasteltes PDF, nicht ein manipulierender Verein. Gegenüber Verband oder
Behörde begründet er keine eigene Beweiskraft, weil der Prüfer dem Server des
Vereins vertrauen müsste.

- Der QR enthält Bescheinigungs-ID, `content_hash` und eine Signatur mit dem
  Vereinsschlüssel, damit auch **offline** gegen den öffentlichen Schlüssel geprüft
  werden kann.
- Die öffentliche Prüfseite zeigt **minimal**: gültig ja/nein, Zeitraum, Anzahl der
  Termine, Ausstellungsdatum, ausstellender Verein, Name allenfalls abgekürzt. Wer ein
  verlorenes PDF findet, darf nicht erfahren, an welchen Abenden eine Person wo war.
- `verification_code` ist kurz und undurchratbar, nie die UUID.

### Einordnung

Der Verein stellt **keine** Bedürfnisbescheinigung aus. Nach §14 WaffG bescheinigt der
anerkannte Schießsportverband (§15 WaffG) der Behörde das Bedürfnis; der Verein liefert
dem Verband den Nachweis über die Trainingsteilnahme. Das erzeugte PDF ist also ein
Vereinsnachweis gegenüber dem Verband, kein behördliches Dokument. DSB und BDS haben
eigene Formulare — der Export muss sich daran anpassen lassen.

## Endpunkte

```
# Kern — Sessions
POST   /api/v1/attendance/sessions                 anlegen (board+)
GET    /api/v1/attendance/sessions                 ?from&to&division_id&status
GET    /api/v1/attendance/sessions/{id}
PATCH  /api/v1/attendance/sessions/{id}
POST   /api/v1/attendance/sessions/{id}/close      schließen, hashen, ketten
GET    /api/v1/attendance/sessions/{id}/records

# Kern — Check-in
POST   /api/v1/attendance/sessions/{id}/check-in   {member_id} | {code}
POST   /api/v1/attendance/records/{id}/check-out
PATCH  /api/v1/attendance/records/{id}             korrigieren (board+, auditiert)
DELETE /api/v1/attendance/records/{id}             soft delete, auditiert, mit Begründung

# Kern — Mitgliedersicht
GET    /api/v1/attendance/me/seed                  24h-Seed für den Offline-QR
GET    /api/v1/attendance/me/records
GET    /api/v1/members/{id}/attendance             Vorstandssicht

# Schießsport-Modul  (hinter require_module("shooting"))
GET    /api/v1/modules/shooting/proof/{member_id}  Live-Auswertung, kein Freeze
POST   /api/v1/modules/shooting/certificates       ausstellen, friert ein
GET    /api/v1/modules/shooting/certificates
GET    /api/v1/modules/shooting/certificates/{id}/pdf
POST   /api/v1/modules/shooting/certificates/{id}/revoke
GET    /api/v1/modules/shooting/range-book         Standbuch-Export CSV/PDF
PATCH  /api/v1/modules/shooting/records/{id}       Disziplin, Waffenkategorie, Schusszahl

# Öffentlich, außerhalb /api/v1
GET    /verify/{verification_code}                 ungeauthentifiziert, rate-limited
```

`require_module("shooting")` löst die aktiven Module eines Vereins als Vereinigung der
`sports.modules` über die Sparten des Vereins auf. Das ist die Verdrahtung, die das
Modulkonzept aus [tenants-and-sports.md](tenants-and-sports.md) erstmals wirksam macht —
sie fällt hier aus dem konkreten Fall ab, statt vorher geraten zu werden.

## DSGVO-Pflichten

- Eintrag im Verzeichnis der Verarbeitungstätigkeiten (Art. 30), beide Zwecke getrennt.
- Information der Mitglieder beim Check-in (Art. 13), sichtbar im Self-Service.
- Auskunft über `GET /api/v1/attendance/me/records`.
- Berichtigung über den auditierten `PATCH`-Pfad.
- Keine automatisierte Einzelentscheidung (Art. 22) — die Bescheinigung stellt ein Mensch aus.

## Offene Punkte

- **Schwellwerte gehören in die Konfiguration, nicht in den Code.** Die geläufige Regel
  („18 Mal in 12 Monaten oder mindestens einmal je Monat") unterscheidet sich je nach
  Bundesland und Behörde, und §14 WaffG wurde mehrfach geändert. Umsetzung über
  `rule_key` plus Regeltabelle; die konkreten Zahlen sind vor Produktivgang mit dem
  Verband gegenzuprüfen. Keine Zahl in einer Migration.
- **Aufbewahrungsdauer** ist mit dem Verband abzustimmen. Der Default von 10 Jahren ist
  eine bewusst gesetzte Annahme, keine geprüfte Vorgabe — der Wert ist pro Verein
  konfigurierbar und damit nachträglich änderbar. Die Spalte
  `tenants.attendance_retention_years` trägt einen Kommentar, der sie als ungeprüfte
  Annahme kennzeichnet; er verschwindet erst, wenn die Vorgabe bestätigt ist. Die
  Begründung der Frist gehört ins Verarbeitungsverzeichnis.
- **Standbuch-/Aufsichtspflichten** ergeben sich aus Standordnung und Verbandsvorgaben
  und variieren. Der Export muss anpassbar bleiben.
- **Stufe 2 (qualifiziertes elektronisches Siegel nach eIDAS Art. 35)** ist
  zurückgestellt. Das Feld `seal` existiert, damit es ohne Migration nachrüstbar ist.
  Ein Organisationssiegel passt inhaltlich besser als eine persönliche qualifizierte
  Signatur, weil es keinen Menschen vor eine Signaturkarte setzt.
- Die rechtliche Bewertung dieses Plans steht aus. Sie gehört zu einem Fachanwalt für
  Waffenrecht bzw. zum Verband.

## Umsetzungsreihenfolge

1. **Kern ohne Kryptografie** — Sessions, Records, `manual`-Check-in, Anwesenheitsliste
   im Web, Audit-Trail (Stufe 0). Sofort für jeden Verein nutzbar, keine App nötig.
2. **Retention** — beide Löschjobs, Tenant-Konfiguration, `context_digest`-Pfad.
3. **Rotierender QR** — Seed-Endpunkt, Codeberechnung, Scanner-PWA, `staff_scan`.
4. **Hash-Kette (Stufe 1)** — Session-Abschluss, Kettenglieder, Zeitstempel-Job.
5. **Schießsport-Modul** — `require_module`, Detailtabelle, §14-Auswertung,
   Bescheinigung mit Prüfcode, öffentliche Prüfseite, Standbuch-Export.
