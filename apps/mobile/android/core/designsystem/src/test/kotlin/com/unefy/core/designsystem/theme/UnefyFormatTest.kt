package com.unefy.core.designsystem.theme

import java.time.ZoneId
import java.util.Locale
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The two shapes of date string the API sends, and the two hours a day in
 * which telling them apart matters.
 */
class UnefyFormatTest {

    private val berlin = ZoneId.of("Europe/Berlin")

    @Test
    fun `a plain date is that day, with no zone applied to it`() {
        // A birthday is a day, not a moment. Shifting it by a zone is how a
        // 1 March becomes a 28 February for somebody west of Greenwich.
        assertEquals(expected("2026-03-01"), UnefyFormat.date("2026-03-01", berlin))
    }

    @Test
    fun `an instant is shown as the day it was, where the reader is`() {
        // 23:20 UTC is already the next day in Berlin. Cutting the string to
        // ten characters printed the 11th under a trail entry dated the 12th.
        assertEquals(expected("2026-08-12"), UnefyFormat.date("2026-08-11T23:20:00Z", berlin))
    }

    @Test
    fun `an instant before midnight local time stays on its own day`() {
        assertEquals(expected("2026-08-11"), UnefyFormat.date("2026-08-11T18:00:00Z", berlin))
    }

    @Test
    fun `something that is neither is handed back untouched`() {
        assertEquals("später", UnefyFormat.date("später", berlin))
        assertEquals("", UnefyFormat.date(null, berlin))
    }

    /**
     * The expectation is built with the same localised formatter rather than a
     * literal: the test is about which *day* is chosen, not about how the JDK
     * on this machine happens to punctuate it.
     */
    private fun expected(isoDay: String): String = java.time.LocalDate.parse(isoDay)
        .format(
            java.time.format.DateTimeFormatter
                .ofLocalizedDate(java.time.format.FormatStyle.MEDIUM)
                .withLocale(Locale.getDefault()),
        )
}
