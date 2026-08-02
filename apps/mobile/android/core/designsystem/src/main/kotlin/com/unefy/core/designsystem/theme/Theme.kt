package com.unefy.core.designsystem.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider

/**
 * The single theme entry point for the app.
 *
 * The palette is monochrome by decision, not by omission: no brand hue, colour
 * only for status. Dynamic Color is deliberately absent too — it would inject
 * the user's wallpaper hue into a design that is hueless on purpose.
 *
 * Light and dark are both first-class. `isSystemInDarkTheme` is the only input;
 * there is no in-app override, so the app follows the system the way Android
 * users expect.
 *
 * `MaterialExpressiveTheme` is not used because it is still `internal` in
 * material3 1.4.0. The expressive character comes from the shape scale, the type
 * scale and [UnefyMotion] instead — all of which work on stable.
 */
@Composable
fun UnefyTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colorScheme = if (darkTheme) UnefyDarkColorScheme else UnefyLightColorScheme
    val extendedColors = if (darkTheme) DarkExtendedColors else LightExtendedColors

    CompositionLocalProvider(LocalUnefyColors provides extendedColors) {
        MaterialTheme(
            colorScheme = colorScheme,
            typography = UnefyTypography,
            shapes = UnefyShapes,
            content = content,
        )
    }
}
