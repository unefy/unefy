# unefy iOS App

Native iOS-App für unefy. Swift 6.2 · SwiftUI · iOS 26 · Xcode 26.

## Setup

Das Xcode-Projekt wird deklarativ via [XcodeGen](https://github.com/yonaskolb/XcodeGen) aus `project.yml` erzeugt.

```bash
# Einmalig:
brew install xcodegen

# Projekt generieren:
cd apps/mobile/ios
xcodegen generate
open unefy.xcodeproj
```

In Xcode das Scheme **`unefy-Dev`** wählen (zeigt auf `http://localhost:8008`) und auf iPhone 16 Simulator laufen lassen.

## Voraussetzungen

- Backend läuft lokal (`docker compose up` im Repo-Root) auf Port 8008
- Ein User mit aktiver Membership existiert in der DB. Check:
  ```bash
  docker compose exec postgres psql -U unefy -d unefy -c \
    "SELECT u.email FROM users u JOIN tenant_memberships tm ON tm.user_id=u.id WHERE tm.is_active;"
  ```

## Dev-Login

Im MVP ist nur **Dev-Login** implementiert:
- E-Mail eines existierenden Users eingeben
- Backend gibt JWT-Pair zurück (access 15 min, refresh 30 Tage)
- Tokens landen im iOS Keychain

Google OAuth / Magic Link / Passkeys kommen in späteren Phasen.

## Struktur

```
unefy/
├── App/            UnefyApp, AppState, RootView
├── Core/
│   ├── Config/     AppConfig (Info.plist → API_BASE_URL)
│   ├── Auth/       TokenManager (Keychain)
│   └── Network/    APIClient, Endpoints, APIError
├── Models/         User, Tenant, Session, Member, APIResponse
├── Features/
│   ├── Auth/       AuthService, AuthViewModel, LoginView
│   └── Members/    MemberRepository, MembersViewModel, MemberListView, MemberDetailView
├── Components/     LoadingState, ErrorView, EmptyState, ErrorMessageMapper
└── Resources/      Localizable.xcstrings (de primary, en fallback)
```

## Config

- `Config/Dev.xcconfig` → `API_BASE_URL=http://localhost:8008`
- `Config/Prod.xcconfig` → `API_BASE_URL=https://api.unefy.de` (Platzhalter)

ATS-Exception für localhost ist im Debug-Build aktiv (siehe `project.yml`).
