package com.unefy.core.designsystem.theme

import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color

/**
 * Neutral ramp, converted from the OKLCH greys in apps/web/app/globals.css.
 * These are the Tailwind `neutral` stops; globals.css is upstream.
 *
 * The design is deliberately hueless — see docs/design-system-android.md.
 * Hue enters only through the status colours below.
 */
internal object Neutral {
    val White = Color(0xFFFFFFFF)
    val N50 = Color(0xFFFAFAFA)
    val N100 = Color(0xFFF5F5F5)
    val N150 = Color(0xFFF0F0F0) // interpolated, no web equivalent
    val N200 = Color(0xFFE5E5E5)
    val N400 = Color(0xFFA1A1A1)
    val N500 = Color(0xFF737373)
    val N800 = Color(0xFF262626)
    val N850 = Color(0xFF1F1F1F) // interpolated
    val N900 = Color(0xFF171717)
    val N950 = Color(0xFF0A0A0A)
    val N960 = Color(0xFF0F0F0F) // interpolated, dark surfaceContainerLow
    val N980 = Color(0xFF050505) // interpolated, dark surfaceContainerLowest
}

/**
 * Status colours. Red is taken from the web `--destructive` token; green and
 * amber are Tailwind stops, because the web theme does not define success or
 * warning yet. Reconcile these when it does.
 */
internal object Status {
    val RedLight = Color(0xFFE7000B)
    val RedDark = Color(0xFFFF6467)
    val RedContainerLight = Color(0xFFFFE2E2)
    val RedContainerDark = Color(0xFF460809)

    val GreenLight = Color(0xFF00A63E)
    val GreenDark = Color(0xFF05DF72)
    val GreenContainerLight = Color(0xFFDCFCE7)
    val GreenContainerDark = Color(0xFF032E15)

    val AmberLight = Color(0xFFE17100)
    val AmberDark = Color(0xFFFFB900)
    val AmberContainerLight = Color(0xFFFEF3C6)
    val AmberContainerDark = Color(0xFF461901)
}

/**
 * Every role is set explicitly. The `lightColorScheme` / `darkColorScheme`
 * functions are used as builders only — none of their defaults survive, since a
 * default Material scheme would introduce the purple this design rejects.
 *
 * `tertiary` intentionally mirrors `secondary`: it is the reserved slot should a
 * single accent hue ever be introduced.
 */
internal val UnefyLightColorScheme = lightColorScheme(
    primary = Neutral.N900,
    onPrimary = Neutral.N50,
    primaryContainer = Neutral.N200,
    onPrimaryContainer = Neutral.N900,
    inversePrimary = Neutral.N200,

    secondary = Neutral.N500,
    onSecondary = Neutral.White,
    secondaryContainer = Neutral.N100,
    onSecondaryContainer = Neutral.N900,

    tertiary = Neutral.N500,
    onTertiary = Neutral.White,
    tertiaryContainer = Neutral.N100,
    onTertiaryContainer = Neutral.N900,

    error = Status.RedLight,
    onError = Neutral.White,
    errorContainer = Status.RedContainerLight,
    onErrorContainer = Neutral.N900,

    background = Neutral.White,
    onBackground = Neutral.N950,
    surface = Neutral.White,
    onSurface = Neutral.N950,
    surfaceVariant = Neutral.N100,
    onSurfaceVariant = Neutral.N500,
    surfaceTint = Neutral.N900,

    inverseSurface = Neutral.N900,
    inverseOnSurface = Neutral.N50,

    outline = Neutral.N400,
    outlineVariant = Neutral.N200,

    surfaceBright = Neutral.White,
    surfaceDim = Neutral.N200,
    surfaceContainerLowest = Neutral.White,
    surfaceContainerLow = Neutral.N50,
    surfaceContainer = Neutral.N100,
    surfaceContainerHigh = Neutral.N150,
    surfaceContainerHighest = Neutral.N200,

    scrim = Neutral.N950,
)

internal val UnefyDarkColorScheme = darkColorScheme(
    primary = Neutral.N200,
    onPrimary = Neutral.N900,
    primaryContainer = Neutral.N800,
    onPrimaryContainer = Neutral.N50,
    inversePrimary = Neutral.N900,

    secondary = Neutral.N400,
    onSecondary = Neutral.N900,
    secondaryContainer = Neutral.N800,
    onSecondaryContainer = Neutral.N50,

    tertiary = Neutral.N400,
    onTertiary = Neutral.N900,
    tertiaryContainer = Neutral.N800,
    onTertiaryContainer = Neutral.N50,

    error = Status.RedDark,
    onError = Neutral.N900,
    errorContainer = Status.RedContainerDark,
    onErrorContainer = Neutral.N50,

    background = Neutral.N950,
    onBackground = Neutral.N50,
    surface = Neutral.N950,
    onSurface = Neutral.N50,
    surfaceVariant = Neutral.N800,
    onSurfaceVariant = Neutral.N400,
    surfaceTint = Neutral.N200,

    inverseSurface = Neutral.N50,
    inverseOnSurface = Neutral.N900,

    outline = Neutral.N500,
    outlineVariant = Color(0x1AFFFFFF), // white at 10%, matching web --border

    surfaceBright = Neutral.N800,
    surfaceDim = Neutral.N980,
    surfaceContainerLowest = Neutral.N980,
    surfaceContainerLow = Neutral.N960,
    surfaceContainer = Neutral.N900,
    surfaceContainerHigh = Neutral.N850,
    surfaceContainerHighest = Neutral.N800,

    scrim = Neutral.N980,
)
