package com.unefy.feature.attendance

import java.time.ZoneId
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Which sessions the scanner may offer.
 *
 * The rule mirrors `_require_within_session` in the backend, and it exists
 * because nothing ever closes a session on its own: an evening nobody closed
 * kept showing up as a chip for weeks, and tapping it filed people onto a date
 * they were not there. The server refuses that now; this keeps the scanner
 * from offering it in the first place.
 */
class SessionTonightTest {

    private val zone = ZoneId.of("Europe/Berlin")

    /** 2026-08-08, 19:00 Berlin. */
    private val now = 1_785_171_600L

    private fun session(opensAt: Long, closesAt: Long) = AttendanceSessionSummary(
        id = "s1",
        title = "Training",
        location = null,
        recordCount = 0,
        opensAtEpochSeconds = opensAt,
        closesAtEpochSeconds = closesAt,
    )

    @Test
    fun `a session running right now is offered`() {
        val running = session(now - 3_600, now + 3_600)
        assertTrue(running.isOnTonight(now, zone))
    }

    /** The failure the fix must not introduce: a late arrival at the door. */
    @Test
    fun `an evening past its planned end is still tonight`() {
        val ranOut = session(now - 10_800, now - 300)
        assertTrue(ranOut.isOnTonight(now, zone))
    }

    @Test
    fun `last month's session is not offered`() {
        val stale = session(now - 30 * 86_400, now - 30 * 86_400 + 14_400)
        assertFalse(stale.isOnTonight(now, zone))
    }

    /** Tomorrow's evening exists, but it is not the one being scanned into. */
    @Test
    fun `a session opening tomorrow is not offered yet`() {
        val tomorrow = session(now + 86_400, now + 86_400 + 14_400)
        assertFalse(tomorrow.isOnTonight(now, zone))
    }

    /**
     * A night session that crosses midnight: after 00:00 the day no longer
     * matches, so only the window can carry it — which is why the rule has two
     * clauses rather than one.
     */
    @Test
    fun `a session running past midnight is offered after midnight`() {
        // 22:00 Berlin to 02:00, checked at 00:30.
        val opens = now + 3 * 3_600
        val closes = opens + 4 * 3_600
        val afterMidnight = opens + 2 * 3_600 + 1_800

        assertTrue(session(opens, closes).isOnTonight(afterMidnight, zone))
    }

    /**
     * A row cached before the window was stored. Offering it beats an empty
     * scanner for someone standing at the range; the server still has the
     * last word.
     */
    @Test
    fun `a cached row with no known window is offered`() {
        assertTrue(session(0, 0).isOnTonight(now, zone))
    }
}
