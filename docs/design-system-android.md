# Android Design System

Concrete design specification for the unefy Android app. Conventions and forbidden patterns live in [apps/mobile/CLAUDE.md](../apps/mobile/CLAUDE.md); this file defines the actual values.

## Direction

**Neutral, type-led, Material 3 Expressive.**

No brand hue. `primary` is near-black in light mode and near-white in dark mode, exactly as the web app already does it. Colour enters the UI only through status roles (error, success, warning) and never for decoration. Hierarchy is carried by typography, whitespace and surface steps.

This is a deliberate choice, not an unfinished state. It gives unefy the editorial, tool-like character of Linear or Vercel rather than the default Material look, and it means the Android app already agrees with the web app without a repaint.

**The risk it carries:** Material 3 leans heavily on tonal colour to express elevation and state. Stripped of hue, a careless implementation reads as flat and cheap. The rules under [Avoiding flatness](#avoiding-flatness) are what prevent that — they are not optional polish.

## Source of truth

Colours are derived from `apps/web/app/globals.css`, which uses OKLCH greys at zero chroma. Converted to sRGB these are exactly the Tailwind `neutral` scale:

| Web token | OKLCH | sRGB | Tailwind |
|-----------|-------|------|----------|
| `--foreground` (light) | `0.145 0 0` | `#0A0A0A` | neutral-950 |
| `--primary` (light) | `0.205 0 0` | `#171717` | neutral-900 |
| `--secondary` (dark) | `0.269 0 0` | `#262626` | neutral-800 |
| `--muted-foreground` (light) | `0.556 0 0` | `#737373` | neutral-500 |
| `--ring` (light) | `0.708 0 0` | `#A1A1A1` | ≈ neutral-400 |
| `--border` (light) | `0.922 0 0` | `#E5E5E5` | neutral-200 |
| `--muted` (light) | `0.97 0 0` | `#F5F5F5` | neutral-100 |
| `--primary` (dark) | `0.985 0 0` | `#FAFAFA` | neutral-50 |

When the web tokens change, these change with them. `globals.css` is upstream.

## Color scheme

Hand-written `ColorScheme` — **not** `lightColorScheme()` defaults and **not** `dynamicLightColorScheme()`. Dynamic Color is off: it would inject the user's wallpaper hue into a deliberately hueless design.

### Light

| M3 role | Value | Notes |
|---------|-------|-------|
| `primary` | `#171717` | Filled buttons, FAB, active states |
| `onPrimary` | `#FAFAFA` | |
| `primaryContainer` | `#E5E5E5` | |
| `onPrimaryContainer` | `#171717` | |
| `secondary` | `#737373` | |
| `onSecondary` | `#FFFFFF` | |
| `secondaryContainer` | `#F5F5F5` | Selected chips, active nav item |
| `onSecondaryContainer` | `#171717` | |
| `tertiary` / `tertiaryContainer` | same as secondary | Reserved. If a single accent hue is ever introduced, it enters here and nowhere else. |
| *accent variant* | deep green, debug toggle | `UnefyAccentLightColorScheme` / `…Dark` in `Accent.kt`. A temporary side-by-side so the neutral-vs-accent question can be answered on a device. One of the two schemes is deleted once it is. |
| `surface` | `#FFFFFF` | |
| `onSurface` | `#0A0A0A` | |
| `onSurfaceVariant` | `#737373` | Metadata, supporting text |
| `surfaceContainerLowest` | `#FFFFFF` | |
| `surfaceContainerLow` | `#FAFAFA` | |
| `surfaceContainer` | `#F5F5F5` | |
| `surfaceContainerHigh` | `#F0F0F0` | Interpolated — no web equivalent |
| `surfaceContainerHighest` | `#E5E5E5` | Pressed / selected rows |
| `outlineVariant` | `#E5E5E5` | Default hairline — the workhorse separator |
| `outline` | `#A1A1A1` | Focus rings, emphasised borders |
| `error` | `#E7000B` | Tailwind red-600, from `--destructive` |
| `onError` | `#FFFFFF` | |
| `errorContainer` | Tailwind red-100 | |

### Dark

| M3 role | Value | Notes |
|---------|-------|-------|
| `primary` | `#E5E5E5` | Inverted, matching web `.dark` |
| `onPrimary` | `#171717` | |
| `primaryContainer` | `#262626` | |
| `onPrimaryContainer` | `#FAFAFA` | |
| `secondary` | `#A1A1A1` | |
| `secondaryContainer` | `#262626` | |
| `onSecondaryContainer` | `#FAFAFA` | |
| `surface` | `#0A0A0A` | |
| `onSurface` | `#FAFAFA` | |
| `onSurfaceVariant` | `#A1A1A1` | |
| `surfaceContainerLowest` | `#050505` | |
| `surfaceContainerLow` | `#0F0F0F` | |
| `surfaceContainer` | `#171717` | Cards, matching web `--card` |
| `surfaceContainerHigh` | `#1F1F1F` | |
| `surfaceContainerHighest` | `#262626` | |
| `outlineVariant` | `#FFFFFF` at 10% | Matching web `--border` in dark |
| `outline` | `#737373` | |
| `error` | `#FF6467` | Lightened for dark, from web `--destructive` |
| `onError` | `#171717` | |

Both schemes must also be provided as **medium and high contrast variants** — Android 14+ exposes a system contrast setting, and a neutral design has less headroom than a coloured one. Ignoring it is an accessibility failure, not a nice-to-have.

### Extended colors

Material 3 has no `success` or `warning` role. Both are needed (dues paid, sync pending, licence expiring). Define them as an extension exposed through a `LocalUnefyColors` composition local — never as literals at the call site:

| Extension role | Light | Dark |
|----------------|-------|------|
| `success` / `onSuccess` | Tailwind green-600 / white | green-400 / neutral-900 |
| `successContainer` | green-100 | green-950 |
| `warning` / `onWarning` | Tailwind amber-600 / neutral-900 | amber-400 / neutral-900 |
| `warningContainer` | amber-100 | amber-950 |

The iOS app currently scatters `Color.systemGreen` and `.orange` through feature code with no definition anywhere. Android must not repeat that.

### Data visualization

The web app already defines `--chart-1` through `--chart-5` as five greys (`#DEDEDE`, `#737373`, `#5C5C5C`, `#4D4D4D`, `#3D3D3D` — OKLCH 0.87 / 0.556 / 0.439 / 0.371 / 0.269). Reuse that ramp. For shooting-result charts, encode by position and shape, not hue.

## Typography

**Fira Sans** — matching the web app, which loads weights 300–700. Humanist and characterful, which matters more here than in a coloured design because type does the hierarchy work.

Bundled as font resources in `core/designsystem/src/main/res/font/`, not loaded through the downloadable-fonts provider: the app must render correctly offline and on first launch, and the provider is not guaranteed to be present. Only the three weights the scale uses are shipped (400/500/600, ~1.4 MB); adding one costs ~450 KB, so it happens when a style needs it. Numerics use bundled Geist Mono.

Type scale — map Fira Sans onto the M3 `Typography` roles, with 500 and 600 as the only bold weights (600 for large titles, 500 for labels; 700 is too heavy against Fira's already-sturdy forms):

| M3 role | Size / line height | Weight | Use |
|---------|-------------------|--------|-----|
| `displaySmall` | 36 / 44 | 600 | Scan result score, single hero number |
| `headlineMedium` | 28 / 36 | 600 | Large screen titles in the collapsing app bar |
| `headlineSmall` | 24 / 32 | 600 | Section headers |
| `titleLarge` | 20 / 28 | 500 | Collapsed app bar title |
| `titleMedium` | 16 / 24 | 500 | List row primary text, dialog titles |
| `bodyLarge` | 16 / 24 | 400 | Body copy |
| `bodyMedium` | 14 / 20 | 400 | List row secondary text |
| `labelLarge` | 14 / 20 | 500 | Buttons |
| `labelMedium` | 12 / 16 | 500 | Chips, badges, metadata |

Numeric data — member numbers, scores, ring values, currency — uses `Geist Mono` with tabular figures so columns align and values don't shift while syncing.

## Shape

Derived from the web `--radius: 0.625rem` (10px) and its multiplier scale:

| M3 shape | Value | Applied to |
|----------|-------|------------|
| `extraSmall` | 6dp | Badges, small chips |
| `small` | 8dp | Text fields, dense controls |
| `medium` | 10dp | Buttons, standard containers |
| `large` | 14dp | Cards, bottom sheets |
| `extraLarge` | 18dp | FAB, modal surfaces, hero containers |

Chips and avatars are fully rounded (pill / circle). M3 Expressive's shape morphing on press is welcome on the FAB and primary actions — it is one of the few expressive signals available without colour.

## Motion

Use the spring specs in `UnefyMotion` — `spatial()` for anything that moves or resizes, `effects()` for colour and alpha. Never hand-written `tween` durations: spring-based motion is what reads as expressive, and in a neutral palette motion carries proportionally more of the personality.

**Why not `MotionScheme.expressive()`:** `MaterialExpressiveTheme` and `MotionScheme` are still `internal` in material3 1.4.0, which is what Compose BOM 2026.03.01 resolves. The only versions above it are `1.5.0-alpha*`, and an alpha does not belong in the foundation of the app. `UnefyMotion` is the stable equivalent — the goal was spring-based motion, not that specific API. Revisit when the expressive theme APIs go public.

Material 3 Expressive's *styling* is unaffected by this: shape, type and colour are all fully expressible on 1.4.0. It is only the motion-scheme plumbing that is gated.

Required, not decorative:

- **Shared element transitions** between list row and detail screen (member list → member detail, session → result). This is the single highest-impact craft detail in the app.
- **Predictive back** wired through so the transition reverses under the user's finger.
- **Staggered list entry** on first load only — never on every recomposition or scroll.
- **Score reveal** on the scan result screen: hits appear in sequence, not all at once.

## Avoiding flatness

The rules that make a hueless Material design look deliberate rather than unfinished. These are the acceptance criteria for any screen review:

1. **Elevation through surface steps, never shadows.** `surfaceContainerLow` → `Container` → `High` → `Highest`. No `shadowElevation` above 0 except on genuinely floating surfaces (FAB, menus).
2. **Hairlines over cards for dense content.** Member and event lists are bordered rows on `surface`, not a stack of rounded cards. Cards are for genuinely bounded objects (a scan result, a dues summary).
3. **One emphasis per screen.** A single filled `primary` action. Everything else is outlined, text, or tonal. Two black filled buttons on one screen is the most common way this design fails.
4. **Whitespace on a 4dp grid**, 16dp screen margins, 8dp between related elements, 24dp between groups. In a neutral design, spacing is what groups content — there is no colour to do it.
5. **Skeletons matched to real content geometry.** A skeleton that doesn't match the row it becomes is worse than none.
6. **Empty states are designed**, with a headline naming the space, one line of body copy and a verb CTA. No "Keine Daten vorhanden".
7. **State is legible without colour.** Selected, pressed, disabled and focused must each be distinguishable in greyscale — which is the whole palette. Verify on the screenshot tests, not by eye.
8. **Adaptive at every window size class.** `ListDetailPaneScaffold` for members and events; `NavigationSuiteScaffold` switching bar → rail → drawer. Required at targetSdk 36 (see CLAUDE.md build requirements).

## Verification

- **Roborazzi screenshot tests** for every screen in the matrix: light / dark × phone / tablet / foldable × default / high contrast. This matrix is the reason the design decisions above are testable rather than opinions.
- **Contrast**: every text-on-surface pair verified against WCAG AA. A neutral palette makes this both easier to reason about and easier to get wrong at the `onSurfaceVariant` end.
- **Greyscale state check**: screenshot the interaction states and confirm each is distinguishable.
