# Mobile Apps: Native (iOS + Android)

Native mobile apps for unefy club management. Two separate codebases — Swift/SwiftUI (iOS) and Kotlin/Jetpack Compose (Android). Communicate directly with the FastAPI backend (no BFF).

## Core Principles

1. **Truly Native**: Platform-native UI frameworks, patterns, and conventions — no cross-platform compromise
2. **Performance**: Native rendering, no bridges, 60fps minimum, instant app start
3. **Offline-Capable**: Critical data cached locally, app usable without network
4. **AI On-Device**: ML models run locally (Core ML / MediaPipe + LiteRT), cloud only as fallback
5. **Platform Excellence**: Full utilization of platform-specific APIs and design guidelines

## Tech Stack

### iOS (Swift)

| Layer | Technology |
|-------|-----------|
| Language | Swift 6.2 (Approachable Concurrency, default `@MainActor`) |
| UI | SwiftUI with **Liquid Glass** design language (iOS 26+) |
| Architecture | MVVM with `@Observable` macro |
| Navigation | NavigationStack / NavigationSplitView |
| Networking | URLSession + async/await |
| Persistence | SwiftData (local cache) |
| Keychain | Security framework (token storage) |
| Camera | AVFoundation + Vision framework |
| ML (custom models) | Core ML 4.0 (up to 45 TOPS on-device) |
| ML (on-device LLM) | Foundation Models framework (Apple's ~3B LLM, offline, free) |
| Auth | AuthenticationServices (passkeys), ASWebAuthenticationSession (OAuth) |
| Push | APNs via UserNotifications |
| Biometrics | LocalAuthentication (Face ID / Touch ID) |
| Testing | Swift Testing framework (primary) + XCTest (legacy) |
| IDE | Xcode 26.4 |
| Dependencies | Swift Package Manager (SPM) |
| Min Target | iOS 26 (required for Liquid Glass + Foundation Models) |
| Build SDK | iOS 26 SDK (required for App Store submission from April 2026) |

### Android (Kotlin)

| Layer | Technology |
|-------|-----------|
| Language | Kotlin 2.x (K2 compiler, KSP — no kapt) |
| UI | Jetpack Compose with **Material 3 Expressive** |
| Adaptive UI | `material3-adaptive` + `WindowSizeClass` (not optional — see Build Requirements) |
| Architecture | MVVM with ViewModel + StateFlow |
| Navigation | Navigation 3 (stable since 1.0, Nov 2025) — back stack as Compose state |
| Dependency Injection | Hilt (KSP) |
| Networking | Ktor Client + kotlinx.serialization |
| Persistence | Room (local cache) + DataStore (preferences) |
| Secure Storage | Android Keystore (AES-GCM key) + DataStore for ciphertext |
| Camera | CameraX Compose-native (`CameraXViewfinder` composable, stable) |
| ML (custom models) | MediaPipe + LiteRT (formerly TFLite) + ML Kit |
| ML (on-device LLM) | Gemini Nano via AICore (flagships) OR MediaPipe LLM Inference + Gemma 2B (broader) |
| Auth | Credential Manager (Sign in with Google, passkeys) |
| Push | Firebase Cloud Messaging (FCM) |
| Biometrics | BiometricPrompt |
| Testing | JUnit 5 + Compose Testing + Espresso |
| Build | AGP 9.3.1 + Gradle 9.5.0, Kotlin DSL + Version Catalog + convention plugins in `build-logic/` |
| Min Target | API 31 (Android 12) — Dynamic Color and Splash Screen API available natively |
| Build SDK | compileSdk 37 (Android 17), targetSdk 36 — AndroidX AAR metadata requires compiling against 37; targeting stays at 36 |

**Secure storage note:** `androidx.security:security-crypto` (`EncryptedSharedPreferences`) was deprecated in 1.1.0 — all APIs, no further releases, no successor library and no official migration path. Google's guidance is "direct use of Android Keystore". So `TokenManager` owns a hardware-backed, non-exportable AES-GCM key in the Keystore and writes only ciphertext to DataStore. Never store tokens unencrypted.

### Android Build Requirements (Play Store)

These are enforced, not stylistic:

- **Adaptive layouts are mandatory.** At targetSdk 36, Android ignores orientation and resizability restrictions on displays ≥ 600dp. A portrait-only phone app is no longer possible — tablets and foldables must be designed for.
- **16 KB page size.** Native libraries must be 16-KB-aligned for Play uploads at targetSdk 36+. This affects the `.so` files shipped by LiteRT and MediaPipe — pin versions that comply, or uploads are rejected.
- **Edge-to-edge is the default**, not opt-in. Handle window insets explicitly.
- **Predictive back** is active at current targetSdk — affects custom back handlers.
- **targetSdk deadline:** Play requires a recent API level every late summer. Plan one bump per year.

## Architecture (Both Platforms)

### MVVM Pattern

```
View (SwiftUI / Compose)
  ↓ observes
ViewModel (business logic, state management)
  ↓ calls
Repository (data access, caching)
  ↓ calls
API Client (networking) + Local DB (offline cache)
```

| Layer | Responsibility | Rules |
|-------|---------------|-------|
| **View** | UI rendering, user input | No business logic, no API calls |
| **ViewModel** | State management, orchestration | No UI framework imports, no direct API calls |
| **Repository** | Data access, cache strategy | Decides: API vs. local cache |
| **API Client** | HTTP requests, auth headers | Handles token refresh, error mapping |
| **Local DB** | Offline cache, draft storage | Source of truth when offline |

### Shared API Contract

Both apps consume the same backend API. Keep consistency via:
- **Hand-written DTOs and API clients on both platforms** — no code generation. Deliberate choice: lean, readable models that match each platform's conventions (iOS keeps all models under ~260 lines), full control over the response envelope and error mapping.
- **OpenAPI spec** generated from FastAPI → used to *validate*, not to generate. A CI test checks the hand-written DTOs against the spec so backend drift fails the build instead of surfacing as a runtime decoding error.
- **Identical data models** — same field names, types, enums
- **Shared test cases** — same API scenarios tested on both platforms

## Project Structure

### iOS

```
ios/
├── unefy.xcodeproj
├── unefy/
│   ├── App/
│   │   ├── UnefyApp.swift           # App entry point
│   │   └── AppState.swift           # Global app state
│   ├── Features/
│   │   ├── Auth/
│   │   │   ├── Views/
│   │   │   │   ├── LoginView.swift
│   │   │   │   ├── MagicLinkView.swift
│   │   │   │   └── PasskeyButton.swift
│   │   │   ├── AuthViewModel.swift
│   │   │   └── AuthService.swift
│   │   ├── Members/
│   │   │   ├── Views/
│   │   │   │   ├── MemberListView.swift
│   │   │   │   ├── MemberDetailView.swift
│   │   │   │   └── MemberFormView.swift
│   │   │   ├── MembersViewModel.swift
│   │   │   └── MemberRepository.swift
│   │   ├── Events/
│   │   │   └── ...
│   │   ├── Scan/                    # AI target scanning
│   │   │   ├── Views/
│   │   │   │   ├── ScannerView.swift
│   │   │   │   ├── TargetOverlay.swift
│   │   │   │   └── ScanResultView.swift
│   │   │   ├── ScanViewModel.swift
│   │   │   ├── TargetDetector.swift  # Core ML inference
│   │   │   └── ScoringEngine.swift   # Hit → ring calculation
│   │   └── Settings/
│   │       └── ...
│   ├── Core/
│   │   ├── Network/
│   │   │   ├── APIClient.swift       # URLSession wrapper, auth, refresh
│   │   │   ├── APIEndpoints.swift    # Typed endpoint definitions
│   │   │   └── APIError.swift
│   │   ├── Auth/
│   │   │   ├── TokenManager.swift    # Keychain read/write
│   │   │   ├── BiometricAuth.swift
│   │   │   └── PasskeyManager.swift
│   │   ├── Storage/
│   │   │   └── LocalDatabase.swift   # SwiftData container
│   │   └── Extensions/
│   │       └── ...
│   ├── Models/                       # Shared data models
│   │   ├── Member.swift
│   │   ├── Event.swift
│   │   ├── ScanResult.swift
│   │   └── ...
│   ├── Resources/
│   │   ├── MLModels/
│   │   │   └── TargetDetector.mlmodel
│   │   ├── Localizable.xcstrings     # i18n
│   │   └── Assets.xcassets
│   └── Components/                   # Reusable UI components
│       ├── LoadingState.swift
│       ├── ErrorView.swift
│       ├── EmptyState.swift
│       └── ...
└── unefyTests/
    └── ...
```

### Android

```
android/
├── settings.gradle.kts
├── build.gradle.kts
├── gradle/
│   └── libs.versions.toml                    # Version catalog — the only place versions live
├── build-logic/                              # Convention plugins (no config duplicated per module)
│   └── convention/src/main/kotlin/
│       ├── AndroidApplicationConvention.kt
│       ├── AndroidLibraryConvention.kt
│       ├── AndroidComposeConvention.kt
│       ├── AndroidFeatureConvention.kt       # library + compose + hilt + testing, in one plugin
│       └── HiltConvention.kt
├── app/                                      # Thin shell only — no business logic
│   └── src/main/
│       ├── java/com/unefy/app/
│       │   ├── UnefyApplication.kt           # @HiltAndroidApp
│       │   ├── MainActivity.kt               # edge-to-edge, single activity
│       │   └── navigation/
│       │       ├── UnefyNavDisplay.kt        # Navigation 3 NavDisplay + entry providers
│       │       └── TopLevelRoute.kt          # NavigationSuiteScaffold destinations
│       └── res/values/strings.xml            # app-level strings only
├── core/
│   ├── model/                                # Pure Kotlin — domain models, no Android deps
│   │   ├── Member.kt
│   │   ├── Event.kt
│   │   └── ScanResult.kt
│   ├── network/
│   │   ├── ApiClient.kt                      # Ktor HttpClient, envelope decoding
│   │   ├── ApiEndpoints.kt                   # Typed endpoint definitions
│   │   ├── ApiError.kt                       # Error code → typed app error
│   │   └── AuthPlugin.kt                     # Ktor Auth: bearer + refreshTokens
│   ├── database/                             # Room: entities, DAOs, offline cache + write queue
│   ├── datastore/                            # DataStore preferences
│   ├── auth/
│   │   ├── TokenManager.kt                   # Keystore AES-GCM key + ciphertext in DataStore
│   │   ├── BiometricAuth.kt                  # BiometricPrompt
│   │   └── PasskeyManager.kt                 # Credential Manager
│   ├── designsystem/                         # M3 Expressive theme, tokens, shared components
│   │   ├── theme/                            # Color, type, shape, motion; Dynamic Color opt-in
│   │   └── component/
│   │       ├── LoadingState.kt               # Skeletons, not spinners
│   │       ├── ErrorView.kt
│   │       ├── EmptyState.kt
│   │       └── OfflineBanner.kt
│   └── testing/                              # Fakes, fixtures, coroutine + Turbine rules
└── feature/                                  # Each: ui/ + ViewModel + Repository + own strings.xml
    ├── auth/
    │   ├── ui/{LoginScreen,MagicLinkScreen,PasskeyButton}.kt
    │   ├── AuthViewModel.kt
    │   └── AuthRepository.kt
    ├── members/
    │   ├── ui/{MemberListScreen,MemberDetailScreen,MemberFormScreen}.kt
    │   ├── MembersViewModel.kt
    │   └── MemberRepository.kt
    ├── events/
    ├── scan/                                 # AI target scanning
    │   ├── ui/{ScannerScreen,TargetOverlay,ScanResultScreen}.kt
    │   ├── ScanViewModel.kt
    │   ├── TargetDetector.kt                 # MediaPipe / LiteRT inference
    │   ├── ScoringEngine.kt                  # Pure geometry — unit-tested, no Android deps
    │   └── src/main/assets/ml/target_detector.tflite
    └── settings/
```

#### Android Module Dependency Rules

Enforced by convention, and the reason for the module split in the first place:

| Module | May depend on | Must never depend on |
|--------|---------------|----------------------|
| `app` | all `feature:*`, `core:designsystem` | — |
| `feature:*` | `core:*` | another `feature:*` |
| `core:network`, `core:database` | `core:model` | any `feature:*`, `core:designsystem` |
| `core:model` | nothing (pure Kotlin) | everything |
| `core:designsystem` | `core:model` | `core:network`, `core:database`, any `feature:*` |

- **Features never talk to each other.** Shared navigation goes through `app`, shared data through `core:*`.
- **`app` stays thin** — Application class, MainActivity, navigation wiring. No screens, no repositories.
- **New feature = new module** using the `AndroidFeatureConvention` plugin, not a package inside an existing one.

## Authentication (Both Platforms)

Both apps authenticate directly against the backend's mobile auth endpoints.

### Token Management

```
Login (Magic Link / Google / Passkey)
  → Backend returns access_token + refresh_token
  → Store in iOS Keychain / Android Keystore (encrypted)
  → Attach access_token to every API request
  → On 401: auto-refresh with refresh_token
  → On refresh failure: redirect to login
```

### Auth Endpoints (consumed by both apps)

```
POST /api/v1/auth/mobile/magic-link/request
POST /api/v1/auth/mobile/magic-link/verify
POST /api/v1/auth/mobile/oauth/google/nonce
POST /api/v1/auth/mobile/oauth/google
POST /api/v1/auth/mobile/passkey/register
POST /api/v1/auth/mobile/passkey/authenticate
POST /api/v1/auth/mobile/refresh
POST /api/v1/auth/mobile/logout
GET  /api/v1/auth/me
```

### MVP Auth Methods
1. **Magic Link / Email OTP** — deep link back into the app
2. **Google** — Credential Manager (Android): reads the accounts already
   signed in on the device, no browser. The backend is handed the resulting ID
   token and checks signature, audience and a nonce it issued itself. iOS still
   to do — ASWebAuthenticationSession or the Google Sign-In SDK, same endpoint.
3. **Passkeys** — AuthenticationServices (iOS) / Credential Manager (Android)

### Roadmap
- Apple Sign-In (required for iOS App Store when other social logins are present)
- Biometric gating: Face ID / Fingerprint to unlock stored tokens
- Device registration & trusted devices
- Session management (view all active devices, remote logout)

## AI / Computer Vision: Target Scoring (Target Detection)

### Use Case
Shooting clubs: Point camera at target → automatic hit detection and ring scoring.

### Architecture

```
Camera Feed
  ↓
Native Camera API (AVFoundation / CameraX)
  ↓
On-Device ML Model (Core ML / TFLite)
  ↓
Detection Results (hit coordinates + confidence)
  ↓
Scoring Engine (coordinates → ring values)
  ↓
UI Overlay (hit markers, ring values, total score)
```

### Implementation Phases

#### Phase 1: Photo Mode (MVP)
- User photographs target
- Image is analyzed on-device
- Hits detected, rings calculated, result displayed
- Save result, share, sync to backend
- **Simpler, more robust, better results than real-time detection**

#### Phase 2: Live Mode
- Camera preview with real-time overlay
- ML model runs on every frame (< 30ms inference)
- Augmented reality: hit points and score displayed live
- Requires optimized model, possibly quantized (INT8)

### ML Model (Target Detection)

| Aspect | iOS | Android |
|--------|-----|---------|
| Format | Core ML 4.0 (`.mlmodel` / `.mlpackage`) | LiteRT/TFLite (`.tflite`) + MediaPipe |
| Runtime | Core ML framework (up to 45 TOPS) | LiteRT + MediaPipe (CPU/GPU/NPU delegates) |
| Acceleration | Neural Engine + GPU | NNAPI / GPU delegate |
| Camera | AVFoundation | CameraX Compose-native (`CameraXViewfinder`) |
| Model Size | < 20 MB (ship in app bundle) | < 20 MB |

**Model Pipeline (separate from app development):**
1. Training data: Photos of various target types with annotated hits
2. Train object detection model (e.g. YOLOv8 / custom)
3. Export to Core ML + TFLite
4. Ship as app asset, update via OTA (without app update)

### On-Device LLM: Apple Foundation Models (iOS)

Apple's Foundation Models framework (iOS 26) provides a ~3B parameter LLM that runs **entirely on-device** — private, offline, free. Use it for intelligent features beyond pure CV:

```swift
import FoundationModels

// Example: Analyze scan results, suggest improvements
let session = LanguageModelSession()
let response = try await session.respond(to: """
  Analyze these shooting results: \(scanResults.description).
  Provide a brief evaluation and improvement tips.
""")
```

**Use cases for unefy:**
- Natural language analysis of shooting results ("Your grouping shows a right-side trend")
- Smart member search ("Show me all members who haven't been active for 3 months")
- Event description generation / summarization
- Guided generation for structured output (e.g. competition reports)
- Tool calling: model calls back into app for data (e.g. fetching member stats)

**Constraints:**
- Only on Apple Intelligence-capable devices (iPhone 15 Pro+, iPad M1+, Mac M1+)
- Not a general chatbot — optimized for language understanding, structured output, tool use
- Provide graceful fallback for devices without Apple Intelligence

### On-Device LLM: Android Strategy

Android has **no single equivalent** to Apple's Foundation Models. Use a tiered approach:

**Tier 1: Gemini Nano (Flagship devices)**
- Available via AICore system service (Google Play Services)
- Supported: Pixel 8 Pro+, Galaxy S24+, select flagships with Snapdragon 8 Gen 3+
- High-level text-in/text-out API via AI Edge SDK
- Model is shared system-wide (~1.7GB, downloaded once via Play Services)
- Multimodal support (text + images) on newer devices

**Tier 2: MediaPipe LLM Inference + Gemma 2B (Broader support)**
- Runs on any device with sufficient RAM (4GB+)
- You bundle or download the model (~1.5GB quantized Gemma 2B)
- More control over the model, but more development effort
- ~10-20 tokens/sec on Snapdragon 8 Gen 3 with GPU delegate

**Tier 3: Cloud fallback (Low-end devices)**
- Backend API proxies to Gemini API / other LLM
- For devices without NPU or insufficient RAM
- Requires network connectivity

```kotlin
// Tiered AI strategy
class AIService(private val context: Context) {

  suspend fun analyze(prompt: String): String {
    return when {
      // Tier 1: Gemini Nano available?
      GeminiNano.isAvailable(context) -> {
        GeminiNano.generateText(prompt)
      }
      // Tier 2: Enough resources for local model?
      deviceHasSufficientResources() -> {
        mediaPipeLLM.generate(prompt)
      }
      // Tier 3: Cloud fallback
      else -> {
        apiClient.post("/api/v1/ai/analyze", AnalyzeRequest(prompt))
      }
    }
  }
}
```

**Use cases (same as iOS):**
- Shooting results analysis and improvement tips
- Smart member search with natural language
- Event description generation / summarization

**Important:** Always implement the cloud fallback (Tier 3) first — it works on ALL devices. Then add on-device tiers as enhancement. The backend should expose an AI endpoint (`/api/v1/ai/...`) that both platforms can use as fallback.

### Android Camera (CameraX Compose-Native)

CameraX now has first-class Compose support — no `AndroidView` wrapper needed:

```kotlin
// Direct Compose integration
CameraXViewfinder(
  surfaceRequest = surfaceRequest,
  modifier = Modifier.fillMaxSize()
)
// Supports tap-to-focus, overlays, and ML analysis pipeline directly
```

### Target Types
Support multiple target standards:
- Air rifle 10m
- Small bore rifle 50m
- Sport pistol 25m
- Air pistol 10m
- Custom targets (configurable ring geometry)

### Scoring Engine (shared logic, implemented natively on each platform)
```
Input: Array of hit coordinates (x, y in normalized image space)
     + Target type (defines ring geometry)
Output: Array of { position, ringValue, confidence }
      + totalScore
      + groupingDiameter
```

Ring calculation is pure geometry — no ML needed:
1. Detect target center and scale from ML output
2. Map hit coordinates to distance from center
3. Look up ring value from target type's ring radii table
4. Calculate grouping statistics

### Privacy & Security
- **No camera frames leave the device** unless user explicitly shares a result
- ML inference is fully offline
- Scan results stored locally, synced to backend only on user action
- Camera permission requested with clear purpose string

## Platform-Specific UI Patterns

### iOS (Human Interface Guidelines + Liquid Glass)

**Liquid Glass** is Apple's new design language (WWDC 2025, iOS 26). It applies automatically to standard controls when building with Xcode 26. For custom views:

```swift
// Apply Liquid Glass to custom views
myView
  .glassEffect(.regular)          // Standard glass material

// Group glass elements that morph together
GlassEffectContainer {
  toolbar
    .glassEffect(.regular, in: .capsule)
    .glassEffectID("nav", in: namespace)
}
```

- **Liquid Glass**: Translucent material with real-time refraction/reflection, applies to nav bars, tab bars, toolbars automatically
- **Navigation**: `NavigationStack` with large titles, swipe-back gesture
- **Lists**: `List` with swipe actions, pull-to-refresh
- **Forms**: `Form` with grouped sections
- **Modals**: `.sheet()` for forms, `.fullScreenCover()` for immersive (scanner)
- **Tab Bar**: `TabView` with SF Symbols (Liquid Glass by default in iOS 26)
- **Search**: `.searchable()` modifier
- **Haptics**: `UIImpactFeedbackGenerator` for actions
- **Loading**: `ProgressView` with `.redacted(reason: .placeholder)` for skeletons
- **3D Layout**: SwiftUI now supports 3D view layout (use sparingly, where it adds value)

### Android (Material 3 Expressive)

**Material 3 Expressive** is the current Material design language — richer motion, new shape and motion tokens, more emphatic component styling. It is the Android counterpart to iOS's Liquid Glass; build on it from the start rather than migrating later.

**Concrete values — colour scheme, type scale, shape and motion tokens — live in [docs/design-system-android.md](../../docs/design-system-android.md). Read it before building any screen.** The short version: the design is deliberately **neutral and type-led** — `primary` is near-black (near-white in dark), derived from the web app's tokens, with hue reserved for status roles only. Typography is **Fira Sans**, matching web. Because the palette carries no hue, typography, surface steps, spacing and motion carry the hierarchy; the "Avoiding flatness" rules in that document are acceptance criteria for screen reviews, not polish.

- **Navigation**: Navigation 3 `NavDisplay` with an explicit back stack held as Compose state
- **Top-level navigation**: `NavigationSuiteScaffold` — adapts between bottom bar, rail and drawer by window size class (required, see Build Requirements)
- **Adaptive detail views**: `ListDetailPaneScaffold` for members/events on tablets and foldables
- **Lists**: `LazyColumn` with swipe-to-dismiss, pull-to-refresh
- **Forms**: editable rows from `core:designsystem/component/Form.kt` — label above value on a hairline, the same geometry `UnefyDetailSection` renders read-only. **Not** `OutlinedTextField`: a screen of outlined boxes with floating labels is the default Material look that docs/design-system-android.md rules out, and it made viewing and editing the same record look like two different apps
- **Editing**: in place on the detail screen, with `UnefySaveBar` appearing once something differs from the record. No edit mode, no pencil icon. Saving per keystroke is deliberately not done — these are a club's records
- **Modals**: `ModalBottomSheet` for forms, full-screen for scanner
- **Search**: `SearchBar` (Material 3)
- **Haptics**: `HapticFeedbackType` via `LocalHapticFeedback`
- **Motion**: the `UnefyMotion` spring specs from `core:designsystem` — no hand-rolled `tween` durations. `MotionScheme.expressive()` is `internal` in material3 1.4.0; see docs/design-system-android.md
- **Transitions**: shared element transitions between list row and detail screen, reversible under predictive back
- **Loading**: Skeleton placeholders matched to the geometry of the content they become, not spinners
- **Dynamic Color**: **off.** It would inject the user's wallpaper hue into a deliberately hueless design. `dynamicLightColorScheme()` / `dynamicDarkColorScheme()` are not used.
- **Contrast**: medium and high contrast scheme variants are required — Android 14+ exposes a system contrast setting, and a neutral palette has less headroom than a coloured one
- **Insets**: edge-to-edge is the default; every screen handles window insets explicitly

### Shared UI Conventions (both platforms)
- Dark mode from day one
- Skeleton/placeholder loading states — not spinners
- Empty states with illustration and call-to-action
- Pull-to-refresh on all list screens
- Swipe actions for common operations (edit, delete)
- Haptic feedback for destructive actions and confirmations
- Offline indicator banner when no network

## Networking

### API Client Pattern (both platforms)

```
// Pseudocode — implemented natively in Swift / Kotlin

class APIClient {
  func request<T: Decodable>(endpoint: Endpoint) async throws -> T {
    // 1. Get access token from secure storage
    // 2. Build request with auth header
    // 3. Execute request
    // 4. If 401 → refresh token → retry once
    // 5. If refresh fails → emit auth expired event → navigate to login
    // 6. Decode response envelope: { data: T } or { error: {...} }
    // 7. Map errors to typed app errors
  }
}
```

### Offline Strategy
- **Read**: Serve from local DB (SwiftData / Room), refresh from API in background
- **Write**: Queue mutations locally, sync when online (optimistic UI)
- **Conflict resolution**: Last-write-wins for simple fields, server-wins for complex data
- **Cache invalidation**: TTL-based + push notification triggered refresh

## Code Conventions

### Swift 6.2 (iOS)

**Approachable Concurrency (Swift 6.2 default):**
- New Xcode 26 projects default to `@MainActor` isolation for everything
- Use `@concurrent` attribute to explicitly opt functions off main actor for parallelism
- Progressive disclosure: sequential code → async/await → actors (only when actually needed)
- Enable via `SWIFT_DEFAULT_ACTOR_ISOLATION` build setting

```swift
// Default: runs on @MainActor (safe, simple)
func loadMembers() async throws -> [Member] {
  return try await apiClient.get("/api/v1/members")
}

// Explicitly concurrent when you need parallelism
@concurrent
func processImage(_ image: CGImage) async -> DetectionResult {
  // Runs off main actor — safe for CPU-intensive work
  return try await targetDetector.detect(in: image)
}
```

- `@Observable` macro for ViewModels
- `async/await` for all async operations — no Combine for new code
- Protocol-oriented design for testability (repository protocols, service protocols)
- SF Symbols for all icons
- `String(localized:)` for all user-facing text (i18n)
- No force unwraps (`!`) except `fatalError` in truly impossible cases
- No implicitly unwrapped optionals
- Access control: `private` by default, widen as needed

### Kotlin (Android)
- Kotlin Coroutines + Flow for async operations
- Jetpack Compose for all UI — no XML layouts
- Hilt (KSP) for dependency injection — constructor injection, `@HiltViewModel` for ViewModels
- `StateFlow` + `MutableStateFlow` for ViewModel state
- `sealed class` / `sealed interface` for UI state modeling
- `kotlinx.serialization` for JSON
- Material 3 Expressive components and theming
- `stringResource()` for all user-facing text (i18n)
- No `!!` (non-null assertion) — use safe calls, `requireNotNull`, or sealed states
- Compose previews for all screens and key components

### Both Platforms
- **Feature-based packaging** — not layer-based (features/members/ not views/members/ + viewmodels/members/)
- **Dependency injection** for all services/repositories — no singletons or static access
- **Error states modeled explicitly** — `sealed class UiState<T> { Loading, Success(data), Error(message) }`
- **No hardcoded strings** — all text via i18n
- **No hardcoded URLs** — API base URL via build config

## Testing

### iOS

| Type | Tool | What |
|------|------|------|
| Unit | Swift Testing / XCTest | ViewModels, Services, Scoring Engine |
| UI | XCUITest | Critical flows (login, member CRUD, scan) |
| Snapshot | swift-snapshot-testing | Key screens in light/dark, various sizes |
| ML | XCTest + test images | Detection accuracy, scoring correctness |

### Android

| Type | Tool | What |
|------|------|------|
| Unit | JUnit 5 + MockK / Turbine | ViewModels, Services, Scoring Engine |
| UI | Compose Testing | Critical flows (login, member CRUD, scan) |
| Screenshot | Paparazzi or Roborazzi | Key screens in light/dark, various sizes |
| ML | JUnit + test images | Detection accuracy, scoring correctness |

### Shared Test Scenarios
Both platforms must pass the same functional test cases:
- [ ] Login via magic link → session persisted → app restart stays logged in
- [ ] Token auto-refresh on 401
- [ ] Member CRUD (create, list, view, edit, delete)
- [ ] Event registration flow
- [ ] Target photo scan → correct ring values
- [ ] Offline: cached data shown, mutations queued
- [ ] Biometric unlock (when implemented)

### Review Checklist (Mobile-specific)
- [ ] Tested on iOS simulator AND Android emulator
- [ ] Tested on real device (especially camera/ML features)
- [ ] No main thread blocking (check with Instruments / Android Profiler)
- [ ] Skeleton/placeholder loading states (not spinners)
- [ ] Error states handled (no crashes on API failure)
- [ ] Offline behavior works
- [ ] Dark mode tested
- [ ] i18n for all user-facing text
- [ ] Haptic feedback for key actions
- [ ] Secure storage for tokens (iOS Keychain / Android Keystore — never UserDefaults, SharedPreferences or unencrypted DataStore)
- [ ] Android: layout verified at phone, tablet and foldable window size classes
- [ ] Android: one filled `primary` action per screen, everything else outlined/text/tonal
- [ ] Android: interaction states (selected, pressed, disabled, focused) distinguishable in greyscale
- [ ] Android: Roborazzi matrix green — light/dark × phone/tablet/foldable × default/high contrast
- [ ] Camera/ML tested with various target types and lighting conditions

## Commands

### iOS
- `xcodebuild -scheme unefy -sdk iphonesimulator build` — Build
- `xcodebuild test -scheme unefy -sdk iphonesimulator -destination 'platform=iOS Simulator,name=iPhone 16'` — Run tests
- `swift build` — SPM packages
- Open in Xcode: `open ios/unefy.xcodeproj`

### Android
Run from `apps/mobile/android/`:

- `./gradlew assembleDebug` — Debug build
- `./gradlew testDebugUnitTest` — Unit tests (all modules)
- `./gradlew :feature:members:testDebugUnitTest` — Unit tests for one module (fast inner loop)
- `./gradlew connectedDebugAndroidTest` — Instrumented tests
- `./gradlew lint` — Android Lint
- `./gradlew ktlintCheck` — Kotlin style check
- `./gradlew verifyRoborazziDebug` / `recordRoborazziDebug` — Screenshot tests: verify / re-record

**Toolchain:** JDK 21 + Android SDK (platform 36, build-tools 36). Neither is installed on this machine yet — `brew install --cask temurin@21 android-studio`.

## Forbidden

### Both Platforms
- Business logic in Views/Screens
- API calls from Views (always go through ViewModel → Repository)
- Hardcoded strings, colors, URLs
- Tokens in non-secure storage
- Camera frames leaving the device without consent
- Force unwraps / non-null assertions without justification
- Blocking main thread for I/O or ML inference
- Spinners instead of skeleton loading states

### iOS-Specific
- UIKit unless absolutely necessary (SwiftUI first)
- Combine for new code (use async/await + `@Observable`)
- `ObservableObject` / `@StateObject` / `@Published` (legacy — use `@Observable` macro)
- `UserDefaults` for sensitive data
- Storyboards or XIBs
- Manually managing concurrency when `@MainActor` default + `@concurrent` suffice

### Android-Specific
- XML layouts (Compose only)
- Java code (Kotlin only)
- `SharedPreferences` or plain DataStore for sensitive data (encrypt with an Android Keystore key)
- `androidx.security:security-crypto` / `EncryptedSharedPreferences` — deprecated, no successor
- XML-based top-level navigation or `NavHost` from Navigation 2 (Navigation 3 only)
- `dynamicLightColorScheme()` / `dynamicDarkColorScheme()` — the design is deliberately hueless
- `lightColorScheme()` / `darkColorScheme()` defaults — the scheme is hand-written, see docs/design-system-android.md
- Literal `Color(0xFF…)` or `.dp` spacing values at the call site — use theme and spacing tokens
- `tween()` with hand-picked durations — use `UnefyMotion.spatial()` / `UnefyMotion.effects()`
- `shadowElevation` on in-flow surfaces — elevation comes from `surfaceContainer*` steps
- `GlobalScope` for coroutines (use `viewModelScope` or structured concurrency)
- `LiveData` for new code (use `StateFlow`)
- `AndroidView` for CameraX (use `CameraXViewfinder` composable)
