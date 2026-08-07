package com.unefy.app.theme

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ThemeModeTest {

    @Test
    fun `system follows the device`() {
        assertTrue(ThemeMode.SYSTEM.isDark(systemInDark = true))
        assertFalse(ThemeMode.SYSTEM.isDark(systemInDark = false))
    }

    @Test
    fun `an override ignores the device`() {
        assertTrue(ThemeMode.DARK.isDark(systemInDark = false))
        assertFalse(ThemeMode.LIGHT.isDark(systemInDark = true))
    }

    @Test
    fun `stored ids survive a reordered enum`() {
        ThemeMode.entries.forEach { mode ->
            assertEquals(mode, ThemeMode.fromId(mode.id))
        }
    }

    /** An empty store, or one written by a future release, must not crash. */
    @Test
    fun `unknown and missing ids fall back to the system setting`() {
        assertEquals(ThemeMode.SYSTEM, ThemeMode.fromId(null))
        assertEquals(ThemeMode.SYSTEM, ThemeMode.fromId("sepia"))
    }
}
