# Google-Anmeldung

Zwei Wege, ein Backend:

| Client | Mechanismus | Endpunkt |
|--------|-------------|----------|
| Web | Redirect-Flow (authlib) | `GET /api/v1/auth/oauth/google` → `/callback` |
| Android | Credential Manager, kein Browser | `POST /api/v1/auth/mobile/oauth/google` |

Beide landen in `app/services/google_identity.py`. Dort steht die Regel, die
auf jedem Weg gelten muss: ein bestehendes Konto wird nur dann mit einer
Google-Identität verknüpft, wenn Google die Adresse als verifiziert meldet.
Sonst könnte sich jemand mit einem unverifizierten Google-Alias ein fremdes
unefy-Konto aneignen.

## Ablauf in der App

1. App holt `POST /api/v1/auth/mobile/oauth/google/nonce`.
2. Credential Manager zeigt die Konten, die auf dem Gerät schon angemeldet
   sind. Erster Durchgang nur mit Konten, die unefy schon benutzt haben
   (`filterByAuthorizedAccounts = true`) — das ist der Ein-Tipp-Fall; findet
   er nichts, öffnet der zweite Durchgang die volle Auswahl.
3. Google gibt ein ID-Token zurück, das die Nonce trägt.
4. App schickt Token + Nonce an `POST /api/v1/auth/mobile/oauth/google`.
5. Server prüft Signatur (Googles JWKS), `iss`, `aud`, Ablauf und die Nonce —
   die ist einmalig und wird beim Einlösen verbraucht. Dann JWT-Paar wie beim
   E-Mail-Code, inklusive 412 „noch keinem Verein zugeordnet“.

Ohne Nonce wäre ein abgefangenes ID-Token beliebig oft gegen dieses Backend
wiederverwendbar; deshalb ist sie Pflicht, nicht optional.

## Einrichtung in der Google Cloud Console

Ein Projekt, zwei OAuth-Clients:

1. **Web-Client** — dessen Client-ID ist `GOOGLE_CLIENT_ID` im Backend *und*
   der `serverClientId` der App. Sie steht im `aud`-Claim des ID-Tokens.
2. **Android-Client** — pro Signaturschlüssel einer, mit Paketname
   `com.unefy.app` und SHA-1-Fingerprint. Diese Client-ID wird nirgends
   eingetragen; sie existiert, damit Google die Anfrage an Paketname und
   Signatur binden kann.

Fingerprints, die gebraucht werden:

```bash
keytool -list -v -keystore ~/.android/debug.keystore -alias androiddebugkey -storepass android -keypass android
```

Für Releases kommt der Fingerprint aus Play App Signing dazu — den gibt es
erst nach dem ersten Upload (Play Console → Setup → App-Integrität).

Client-ID in den Build geben, **nicht** in eine getrackte Datei:

```bash
echo 'unefy.googleServerClientId=123-abc.apps.googleusercontent.com' >> apps/mobile/android/local.properties
```

Ohne diesen Wert baut die App normal, zeigt aber keinen Google-Knopf.

## Selbst gehostet

Die Client-ID hängt am Signaturschlüssel der App, nicht am Server. Daraus
folgen zwei Fälle:

- **Veröffentlichte unefy-App gegen eigenen Server.** Die ID-Tokens tragen die
  Client-ID des App-Projekts, nicht die des Betreibers. Der Server muss sie
  zusätzlich akzeptieren:
  `GOOGLE_MOBILE_CLIENT_IDS=["<client-id-der-app>"]`.
- **Eigener App-Build.** Eigenes Google-Cloud-Projekt, eigener Web- und
  Android-Client, `GOOGLE_CLIENT_ID` und `unefy.googleServerClientId` aus dem
  eigenen Projekt.

Ist gar nichts konfiguriert, antworten beide Mobile-Endpunkte mit
`503 GOOGLE_NOT_CONFIGURED` — die App sagt dann „nicht verfügbar“ statt „hat
nicht geklappt“, und der E-Mail-Code bleibt unberührt.
