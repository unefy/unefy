package com.unefy.feature.attendance

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * What one row of the checked-in list says about itself.
 *
 * Worth its own test because the interesting case is a wrong label rather than a
 * missing one: before the self-entry was introduced the choice was
 * `staff_scan → "Gescannt"` and *everything else* → "Von Hand", so a supervisor's
 * own attendance read as a record somebody else had made. Nothing crashes, nothing
 * looks broken, and the screen states the one thing that is not true.
 */
class CheckedInRowLabelTest {

    private fun entry(method: String, pending: Boolean = false) = CheckedInEntry(
        key = "k",
        memberId = "m",
        memberName = "Erika Beispiel",
        method = method,
        checkedInAtEpochSeconds = 0,
        pending = pending,
    )

    @Test
    fun `a self-entry says so instead of reading as somebody else's tick`() {
        assertEquals(R.string.scanner_row_self, rowLabelFor(entry("self")))
    }

    @Test
    fun `a scan and a tick keep their own words`() {
        assertEquals(R.string.scanner_row_scanned, rowLabelFor(entry("staff_scan")))
        assertEquals(R.string.scanner_row_manual, rowLabelFor(entry("manual")))
    }

    @Test
    fun `a method this version does not know is described as a tick`() {
        // The weakest available description, which is the right way to be wrong:
        // `venue_scan` and `nfc_tap` exist in the backend's taxonomy and are not
        // built, and an old app must not describe a future record as more than it
        // can vouch for.
        assertEquals(R.string.scanner_row_manual, rowLabelFor(entry("venue_scan")))
    }

    @Test
    fun `waiting beats the method`() {
        // For a queued row the method is still the app's guess — the server has
        // not answered yet, and "Wartet" is the only honest thing on it.
        assertEquals(R.string.scanner_row_pending, rowLabelFor(entry("self", pending = true)))
    }
}
