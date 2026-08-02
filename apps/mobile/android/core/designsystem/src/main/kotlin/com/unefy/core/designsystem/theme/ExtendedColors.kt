package com.unefy.core.designsystem.theme

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

/**
 * Material 3 has no `success` or `warning` role, but the app needs both (dues
 * paid, sync pending, licence expiring). They are exposed here so no call site
 * ever writes a literal colour.
 *
 * The iOS app currently scatters `Color.systemGreen` and `.orange` through
 * feature code with no central definition. Do not repeat that here.
 */
@Immutable
data class UnefyExtendedColors(
    val success: Color,
    val onSuccess: Color,
    val successContainer: Color,
    val onSuccessContainer: Color,
    val warning: Color,
    val onWarning: Color,
    val warningContainer: Color,
    val onWarningContainer: Color,
)

internal val LightExtendedColors = UnefyExtendedColors(
    success = Status.GreenLight,
    onSuccess = Neutral.White,
    successContainer = Status.GreenContainerLight,
    onSuccessContainer = Neutral.N900,
    warning = Status.AmberLight,
    onWarning = Neutral.White,
    warningContainer = Status.AmberContainerLight,
    onWarningContainer = Neutral.N900,
)

internal val DarkExtendedColors = UnefyExtendedColors(
    success = Status.GreenDark,
    onSuccess = Neutral.N900,
    successContainer = Status.GreenContainerDark,
    onSuccessContainer = Neutral.N50,
    warning = Status.AmberDark,
    onWarning = Neutral.N900,
    warningContainer = Status.AmberContainerDark,
    onWarningContainer = Neutral.N50,
)

/**
 * Not `compositionLocalOf` with a default: reading this outside [UnefyTheme] is
 * a bug and should fail loudly rather than silently render the wrong colour.
 */
val LocalUnefyColors = staticCompositionLocalOf<UnefyExtendedColors> {
    error("LocalUnefyColors accessed outside of UnefyTheme")
}
