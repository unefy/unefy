package com.unefy.feature.attendance

import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiResult
import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.serialization.kotlinx.json.json
import java.time.Instant
import java.time.ZoneId
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
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

/**
 * Opening an evening where there is no signal.
 *
 * The gap this closes was total: no session meant nothing to check into, and
 * with nothing to check into the check-in queue never got the chance to buffer
 * anything either. The evening went unrecorded unless somebody found a laptop.
 */
class OfflineSessionCreationTest {

    /** 2026-08-08, 19:00 Berlin — the same instant SessionTonightTest uses. */
    private val NOW = 1_785_171_600L

    private val cache = FakeCachedSessionDao()
    private val writes = FakeWriteQueue()

    private fun repository(engine: MockEngine) = DefaultAttendanceRepository(
        apiClient = ApiClient(HttpClient(engine) { install(ContentNegotiation) { json(Json) } }),
        syncedMembers = FakeSyncedMemberDao(),
        syncCursors = FakeSyncCursorDao(),
        sessionCache = cache,
        recordCache = FakeCachedSessionRecordDao(),
        clock = { NOW },
        writes = writes,
        json = Json,
    )

    @Test
    fun `an evening opened without a connection is cached and queued`() = runTest {
        val offline = MockEngine { throw java.io.IOException("no route to host") }

        val result = repository(offline).createSession(
            title = "Übungsabend",
            opensAt = Instant.ofEpochSecond(NOW).toString(),
            closesAt = Instant.ofEpochSecond(NOW + 8 * 3_600).toString(),
        )

        // Success, not a failure: from where the supervisor stands the evening
        // is open, and the queue is the app's problem rather than theirs.
        assertTrue(result is ApiResult.Success)
        val session = (result as ApiResult.Success).data

        // Cached, so the scanner reads it back a moment later…
        assertEquals(listOf(session.id), cache.rows.map { it.id })
        // …and queued under the same id, so the check-ins buffered against it
        // need no rewriting when it finally goes.
        assertEquals(listOf(session.id), writes.queued.map { it.recordId })
        assertEquals(SESSION_WRITE_ENTITY, writes.queued.single().entity)
        assertTrue(session.isOnTonight(NOW, ZoneId.of("Europe/Berlin")))
    }
}
