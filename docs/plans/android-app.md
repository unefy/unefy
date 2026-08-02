# Plan: Android-App

Stand 2026-08-02. Zweck dieses Dokuments: die App ist weit gekommen, aber die
Orientierung steckte bisher im Gesprächsverlauf. Hier steht, was existiert, was
nachweislich fehlt und in welcher Reihenfolge es weitergeht.

## Stand

Multi-Modul-Gradle-Projekt unter `apps/mobile/android`, AGP 9.3.1 / Gradle 9.5.0,
compileSdk 37, targetSdk 36, minSdk 31. Läuft auf dem Testgerät.

| Bereich | Zustand |
|---|---|
| `core:model` | Member, Event, Dues, Club, Competition, DirectoryEntry, Session, ClubRole |
| `core:network` | Ktor, Envelope-Decoding, Auth-Bearer mit `refreshTokens` |
| `core:auth` | Keystore AES-GCM + DataStore, Refresh per Mutex serialisiert |
| `core:designsystem` | Monochromes Schema aus den Web-Tokens, Fira Sans, Glass-Header/-Leiste |
| `feature:members` | Liste, Detail, eigenes Profil, Mitgliederverzeichnis |
| `feature:events` | Liste, Detail, Selbst-An-/Abmeldung |
| `feature:dues` | Übersicht, Liste, eigene Beiträge |
| `feature:competitions` | Liste, Detail, Scoreboard |
| App-Shell | Nav3, Glass-Leiste, pro Rolle konfigurierbare Navigation per Drag & Drop |

Backend-seitig ergänzt: Mitglieder-Selfservice (`/members/me`, `/members/directory`,
`/dues/me`, `/events/{id}/registrations/me`), Wettkämpfe für Rolle `member`
lesbar, `tenant_sports` (n:m) samt Migration, `GET /club` liefert `sports` +
`modules`.

### Unmittelbare Risiken

1. ~~Alles ist uncommitted.~~ Erledigt — Backend-Selfservice, `tenant_sports`,
   Android und Doku liegen als getrennte Commits vor.
2. ~~`backend/package.json` und `backend/package-lock.json`~~ waren ein
   versehentliches `npm install zod` im Backend-Verzeichnis; `zod` wird nirgends
   im Repo referenziert, beide Dateien sind entfernt.
3. **Das Drag & Drop der Navigation ist nie manuell getestet worden.** Long-Press
   mit anschließendem Ziehen ist per `adb input` nicht zuverlässig
   reproduzierbar. Muss von Hand ausprobiert werden, bevor es als fertig gilt.

## A. Qualitätsschulden, die CLAUDE.md bereits verlangt

Diese Punkte sind keine Politur, sondern bestehende Verstöße gegen die eigenen
Regeln.

1. ~~Instrumentierter Smoke-Test über alle Navigationsziele.~~ **Erledigt**,
   beide Ebenen laufen grün (Gerät SM-S936B, Android 16):
   - `app/src/test/.../EntryProviderCoverageTest` — läuft auf der JVM, also in
     jedem CI-Lauf. Die Keys sind jetzt eine `sealed interface UnefyNavKey`,
     der Test zählt die Subklassen per Reflection auf und verlangt für jede
     einen Treffer im `entryProvider`. Dafür ist der Entry-Graph als
     `unefyEntryProvider(...)` aus dem `@Composable NavHost` herausgezogen —
     er hängt an Callbacks statt am Back-Stack und ist damit ohne Gerät
     aufrufbar. Gegengeprüft: `entry<CompetitionsKey>` entfernt → Test schlägt
     mit `[CompetitionsKey]` fehl.
   - `app/src/androidTest/.../NavigationSmokeTest` — öffnet auf dem Gerät jedes
     für BOARD bzw. MEMBER erlaubte Ziel, die vier Leisten-Tabs direkt und den
     Rest über „Mehr“. Hilt-Testrunner plus `TestNetworkModule`, das per
     `@TestInstallIn` nur die Ktor-Engine gegen `MockEngine` tauscht — echte
     Repositories, echtes Envelope-Decoding, feste Antworten. Gegengeprüft:
     ein Ziel auf eine werfende Composable gezeigt → Test schlägt fehl, der
     JVM-Test bleibt grün. Genau die Lücke, die er schließen soll.

   Fallstricke, die dabei Zeit gekostet haben:
   - **`HiltTestActivity` gehört in `src/debug`, nicht in `androidTest`.** Eine
     im Test-APK deklarierte Activity läuft im Prozess `com.unefy.app.test`,
     und Instrumentation aus `com.unefy.app` weigert sich, sie zu starten.
   - **Tabs per `Role.Tab` ansprechen, nicht per Text.** Der Reiter „Termine“
     und die Überschrift „Termine“ sind zwei Treffer, sobald der Screen offen
     ist.
   - Der Test schreibt die Navigationsanordnung in den DataStore des Geräts —
     die Leiste muss in einem bekannten Zustand sein. Auf einem Gerät, auf dem
     die App auch von Hand benutzt wird, setzt das die Anordnung zurück.
   - Es gibt weder AVD noch System-Image auf der Maschine; `connectedCheck`
     braucht also das Testgerät.
2. **Unit-Tests für die ViewModels** (JUnit + Turbine). Aktuell sechs
   Testdateien im ganzen Projekt. Vorgabe: 80 % für Logik, 100 % für Auth. Der
   `TokenManager` ist die riskanteste ungetestete Stelle (Refresh-Serialisierung,
   Unterscheidung „Token tot“ vs. „Netz weg“).
3. **OpenAPI-Drift-Test.** CLAUDE.md schreibt vor, dass die handgeschriebenen
   DTOs gegen die FastAPI-Spec validiert werden, damit Backend-Drift den Build
   bricht statt zur Laufzeit als Decoding-Fehler aufzutauchen. Existiert nicht.
4. **Adaptive Layouts.** Der Rail-Zweig für breite Fenster ist implementiert,
   aber nie gesehen. `ListDetailPaneScaffold` für Mitglieder/Termine fehlt
   ganz. Das ist bei targetSdk 36 eine Play-Anforderung, keine Kür.
5. **Roborazzi-Matrix** (hell/dunkel × Telefon/Tablet/Foldable ×
   Standard/hoher Kontrast). Es gibt keine Screenshot-Tests.
6. **Kontrast-Varianten** des Farbschemas (mittel/hoch). Android 14+ hat eine
   System-Kontrasteinstellung, und ein hueloses Schema hat weniger Reserve als
   ein farbiges. In `docs/design-system-android.md` gefordert, nicht umgesetzt.

## B. Funktionale Lücken

- **Offline.** Room, Cache und Write-Queue fehlen vollständig. Ohne Netz ist die
  App leer, obwohl „Offline-Capable“ als Kernprinzip in CLAUDE.md steht.
  Reihenfolge: Lesen aus Room mit Hintergrund-Refresh zuerst, Write-Queue danach.
- **Die App ist fast nur lesend.** Außer der eigenen Terminanmeldung gibt es
  kein Anlegen oder Bearbeiten — keine Mitglieder, keine Termine, keine
  Wettkämpfe. Für Vorstandsrollen ist das die auffälligste Lücke.
- **Auth.** Nur der Dev-Weg. Google OAuth (Custom Tabs), Passkeys (Credential
  Manager) und biometrisches Entsperren fehlen.
- **Anwesenheit.** Das Backend hat Sessions und Check-in (Commit `8897d40`), die
  App nichts davon. Naheliegendster nächster Feature-Block, weil das Backend
  fertig ist.
- **Schießnachweis / Waffenbesitz** nach `docs/plans/attendance-and-shooting-proof.md`
  — Backend geplant, App noch gar nicht.
- **Push (FCM)** fehlt.
- **Zielscheiben-Scan** (CameraX + LiteRT) — Phase 1 laut CLAUDE.md, noch nicht
  begonnen.
- **Mitgliederverzeichnis** ist nur über „Mehr“ erreichbar; ein Einstieg vom
  eigenen Profil wäre naheliegend.
- **Sportarten-Auswahl im Web-Admin fehlt**, deshalb ist `PUT /club/sports`
  bisher nur per API bedienbar.

## C. Design

- **Light Mode** existiert über die Systemeinstellung, wurde aber nie auf dem
  Gerät durchgesehen.
- **Glass für Bottom Sheets** — sobald es welche gibt.
- Die „Avoiding flatness“-Kriterien aus `docs/design-system-android.md` sind als
  Abnahmekriterien gedacht, aber noch nie als Durchgang über alle Screens
  angewendet worden.

## D. Offene Entscheidungen

- Navigations-Anordnung wird **pro Rolle** gespeichert. Wenn jemand die Rolle
  wechselt, sieht er eine andere Leiste. Gewollt?
- Reihenfolge Offline vor Schreiben oder umgekehrt? Schreiben ohne Queue ist
  einfacher, muss aber später angefasst werden.
- iOS: existiert nicht. Erst wenn Android inhaltlich steht, oder parallel?

## Arbeitsweise (Lehren aus dem bisherigen Verlauf)

- **Jede Skript-Ersetzung braucht ein `assert` dahinter.** Eine Ersetzung, deren
  Anker nicht mehr passt, tut still nichts, kompiliert und stürzt erst zur
  Laufzeit ab. Genau so entstand der `CompetitionsKey`-Absturz.
- **Vor jeder Eingabe ans Gerät den Vordergrund prüfen:**
  `adb shell dumpsys activity activities | grep ResumedActivity` — dieses Gerät
  meldet `ResumedActivity`, nicht `topResumedActivity`. Zweimal sind Taps in die
  Vordergrund-App des Nutzers gegangen. Gerät nie entsperren.
- Gerät hängt per WLAN-Debugging; `./gradlew installDebug` genügt, kein manuelles
  APK-Kopieren. Der **Release-Build erreicht ein Cleartext-Dev-Backend nicht** —
  die Network-Security-Ausnahme gilt nur für Debug.
- `material3` 1.4.0: `MaterialExpressiveTheme` und `MotionScheme` sind
  `internal`; stattdessen `UnefyMotion`. `NavigationSuiteScaffold` hat zwei
  Overloads, benannte Parameter binden an das falsche.
