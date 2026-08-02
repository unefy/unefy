package com.unefy.app.nav

import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect

/**
 * Drag state shared between the section grid and the navigation bar.
 *
 * They live in different subtrees — the grid is inside a screen, the bar is in
 * the shell around every screen — so a drag from one to the other cannot be a
 * local gesture. This is the piece both sides talk to: the grid reports what is
 * being dragged and where the finger is, the bar reports where it is, and the
 * shell draws the thing under the finger.
 *
 * Positions are in root coordinates, because that is the only frame both sides
 * agree on.
 */
@Stable
class NavDragState {
    /** The section under the finger, or null when nothing is being dragged. */
    var dragged: TopLevel? by mutableStateOf(null)
        private set

    /** Finger position in root coordinates. */
    var position: Offset by mutableStateOf(Offset.Zero)
        private set

    /** The bar's bounds in root coordinates, published by the shell. */
    var barBounds: Rect by mutableStateOf(Rect.Zero)

    /** How many slots the bar currently shows, "more" included. */
    var barSlots: Int by mutableStateOf(1)

    fun begin(destination: TopLevel, at: Offset) {
        dragged = destination
        position = at
    }

    fun moveBy(delta: Offset) {
        position += delta
    }

    fun cancel() {
        dragged = null
    }

    /**
     * Which slot the finger is over, or null when it is not over the bar.
     *
     * Derived from x within the bar rather than from hit-testing the items: the
     * bar's slots are evenly spaced, so arithmetic is both simpler and immune to
     * the items' own gesture handling.
     */
    fun dropIndexOrNull(): Int? {
        if (dragged == null || barBounds.isEmpty) return null
        // Two rectangles, deliberately. Hitting an 80dp pill that a fingertip
        // covers completely is precision work nobody should have to do, so the
        // zone that counts as "over the bar" is inflated on every side — the bar
        // floats, so overshooting below or beside it is the normal gesture, not
        // a miss. The slot is still derived from the bar's own bounds, because
        // those are what the user sees; x is clamped into them.
        val zone = barBounds.inflate(DROP_ZONE_SLACK)
        if (!zone.contains(position)) return null
        val slotWidth = barBounds.width / barSlots
        val x = position.x.coerceIn(barBounds.left, barBounds.right - 1f)
        val slot = ((x - barBounds.left) / slotWidth).toInt()
        // The last slot is "more" — not a destination, so a drop there means
        // "at the end" rather than replacing it.
        return slot.coerceIn(0, barSlots - 2)
    }

    private companion object {
        /** Pixels around the bar that still count as being over it. */
        const val DROP_ZONE_SLACK = 140f
    }
}

val LocalNavDragState = staticCompositionLocalOf<NavDragState?> { null }
