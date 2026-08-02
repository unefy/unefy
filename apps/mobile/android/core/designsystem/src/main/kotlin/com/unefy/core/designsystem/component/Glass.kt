package com.unefy.core.designsystem.component

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.HazeStyle
import dev.chrisbanes.haze.materials.HazeMaterials

/**
 * The blur source shared across the app shell.
 *
 * It has to be shared: the header lives inside a screen while the navigation bar
 * lives in the shell around all of them, and both blur the same scrolling list.
 * Two separate states would each see only their own subtree — the bar would have
 * nothing to blur.
 *
 * Null when no shell provides one, in which case a screen falls back to a local
 * state so previews and tests still render.
 */
val LocalHazeState = staticCompositionLocalOf<HazeState?> { null }

/**
 * Height of the floating navigation bar, published by the shell.
 *
 * A list has to scroll *behind* a glass bar, so it cannot rely on Scaffold
 * insets to keep clear of it — it pads its content by this instead. Zero when
 * the shell uses a rail, which sits beside the content rather than over it.
 */
val LocalGlassBarHeight = staticCompositionLocalOf { 0.dp }

/**
 * One glass material for the whole app.
 *
 * `thin` on purpose: the point is that a hint of what is underneath stays
 * visible. Thicker materials hide the content and the surface stops reading as
 * glass and starts reading as a grey bar.
 */
@Composable
fun unefyGlassStyle(): HazeStyle = HazeMaterials.thin(MaterialTheme.colorScheme.surface)

/** Padding a scrolling list needs at the bottom to clear a floating bar. */
val glassBarClearance: Dp
    @Composable get() = LocalGlassBarHeight.current
