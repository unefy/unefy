package com.unefy.core.designsystem.theme

import androidx.compose.animation.core.DurationBasedAnimationSpec
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.SpringSpec
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween

/**
 * Motion specs for the whole app.
 *
 * Material 3 Expressive's `MotionScheme` / `MaterialExpressiveTheme` are still
 * `internal` in material3 1.4.0 — the expressive theme API is not public on
 * stable, and pulling in a 1.5.0 alpha for it is not worth the risk in the
 * foundation of the app. These spring specs are the stable equivalent: the point
 * was never the API, it was spring-based motion instead of hand-picked
 * durations. Revisit when the expressive APIs go public.
 *
 * Because the palette carries no hue, motion carries proportionally more of the
 * app's character. Use [spatial] for anything that moves or resizes, [effects]
 * for colour and alpha.
 */
object UnefyMotion {
    /** Slight overshoot — for position, size and shape changes. */
    private const val SPATIAL_DAMPING = 0.8f
    private const val SPATIAL_STIFFNESS = 380f

    /** No overshoot: colour and alpha should never bounce. */
    private const val EFFECTS_DAMPING = 1f
    private const val EFFECTS_STIFFNESS = 1600f

    fun <T> spatial(): SpringSpec<T> = spring(
        dampingRatio = SPATIAL_DAMPING,
        stiffness = SPATIAL_STIFFNESS,
    )

    fun <T> effects(): SpringSpec<T> = spring(
        dampingRatio = EFFECTS_DAMPING,
        stiffness = EFFECTS_STIFFNESS,
    )

    /**
     * The one place a duration is allowed. `infiniteRepeatable` only accepts a
     * duration-based spec, so a looping skeleton shimmer cannot be a spring. The
     * rule against `tween` is about arbitrary durations scattered across call
     * sites — keeping this single value here is what the rule is protecting.
     */
    fun <T> shimmer(): DurationBasedAnimationSpec<T> = tween(
        durationMillis = SHIMMER_DURATION_MS,
        easing = LinearEasing,
    )

    private const val SHIMMER_DURATION_MS = 900
}
