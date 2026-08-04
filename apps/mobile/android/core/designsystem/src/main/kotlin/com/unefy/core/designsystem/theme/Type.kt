package com.unefy.core.designsystem.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import com.unefy.core.designsystem.R
import androidx.compose.ui.text.style.LineHeightStyle
import androidx.compose.ui.unit.sp

/**
 * **Fira Sans**, matching the web app. Bundled rather than loaded through the
 * downloadable-fonts provider: the app must render correctly offline and on
 * first launch, and the provider is not guaranteed to be present on a device.
 *
 * Only the three weights the type scale actually uses are shipped. The web app
 * loads 300-700; adding a weight here means adding ~450 KB to the APK, so it
 * happens when a style needs it, not preemptively.
 */
internal val UnefySansFamily = FontFamily(
    Font(R.font.fira_sans_regular, FontWeight.Normal),
    Font(R.font.fira_sans_medium, FontWeight.Medium),
    Font(R.font.fira_sans_semibold, FontWeight.SemiBold),
)

/** Geist Mono, also matching web. Used only where figures must line up. */
internal val UnefyMonoFamily = FontFamily(Font(R.font.geist_mono))

private val LineHeight = LineHeightStyle(
    alignment = LineHeightStyle.Alignment.Center,
    trim = LineHeightStyle.Trim.None,
)

private fun sans(
    size: Int,
    lineHeight: Int,
    weight: FontWeight,
) = TextStyle(
    fontFamily = UnefySansFamily,
    fontSize = size.sp,
    lineHeight = lineHeight.sp,
    fontWeight = weight,
    lineHeightStyle = LineHeight,
)

/**
 * Only 500 and 600 are used as bold weights. 700 is too heavy against Fira
 * Sans' already sturdy letterforms — see docs/design-system-android.md.
 *
 * **Every slot is filled**, including the ones no screen references directly.
 * Material components reach for them internally — an `OutlinedTextField`'s
 * floating label is `bodySmall`, a badge is `labelSmall` — and any slot left
 * at its default renders Roboto in the middle of a Fira Sans app.
 */
internal val UnefyTypography = Typography(
    displayLarge = sans(57, 64, FontWeight.SemiBold),
    displayMedium = sans(45, 52, FontWeight.SemiBold),
    displaySmall = sans(36, 44, FontWeight.SemiBold),
    headlineLarge = sans(32, 40, FontWeight.SemiBold),
    headlineMedium = sans(28, 36, FontWeight.SemiBold),
    headlineSmall = sans(24, 32, FontWeight.SemiBold),
    titleLarge = sans(20, 28, FontWeight.Medium),
    titleMedium = sans(16, 24, FontWeight.Medium),
    titleSmall = sans(14, 20, FontWeight.Medium),
    bodyLarge = sans(16, 24, FontWeight.Normal),
    bodyMedium = sans(14, 20, FontWeight.Normal),
    bodySmall = sans(12, 16, FontWeight.Normal),
    labelLarge = sans(14, 20, FontWeight.Medium),
    labelMedium = sans(12, 16, FontWeight.Medium),
    labelSmall = sans(11, 16, FontWeight.Medium),
)

/**
 * For identifiers and scores — member numbers, ring values, dates.
 *
 * Not for money: a monospace currency symbol gets a digit's width and drifts
 * away from the amount. [UnefyMoneyTextStyle] handles that case.
 */
val UnefyNumericTextStyle = TextStyle(
    fontFamily = UnefyMonoFamily,
    fontSize = 14.sp,
    lineHeight = 20.sp,
    fontWeight = FontWeight.Normal,
    fontFeatureSettings = "tnum",
)


/**
 * Money. Proportional Fira Sans with tabular figures, so amounts still line up
 * in a column while the currency symbol keeps its natural width.
 */
val UnefyMoneyTextStyle = TextStyle(
    fontFamily = UnefySansFamily,
    fontSize = 16.sp,
    lineHeight = 24.sp,
    fontWeight = FontWeight.Medium,
    fontFeatureSettings = "tnum",
)
