package com.unefy.core.designsystem.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

/**
 * Derived from the web `--radius: 0.625rem` (10dp) and its multiplier scale, so
 * Android and web share one rounding language.
 */
internal val UnefyShapes = Shapes(
    extraSmall = RoundedCornerShape(6.dp),
    small = RoundedCornerShape(8.dp),
    medium = RoundedCornerShape(10.dp),
    large = RoundedCornerShape(14.dp),
    extraLarge = RoundedCornerShape(18.dp),
)

/**
 * Spacing scale. A neutral design has no colour to group content with, so
 * spacing does that work and has to be consistent — never a literal `.dp` at a
 * call site.
 */
object UnefySpacing {
    val hairline = 1.dp
    val xs = 4.dp
    val sm = 8.dp
    val md = 16.dp
    val lg = 24.dp
    val xl = 32.dp

    /** Horizontal screen margin. */
    val screen = 16.dp
}
