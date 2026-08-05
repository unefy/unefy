package com.unefy.feature.attendance

import com.unefy.core.database.PendingCheckIn
import com.unefy.core.database.PendingCheckInDao
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import java.io.IOException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The queue is the only thing standing between a dropped connection and a lost
 * evening's attendance, so its rules are tested rather than assumed: what gets
 * held, what does not, and what the device claims about when it happened.
 */
class CheckInQueueTest {

    private val dao = FakeDao()
    private val repository = FakeRepository()
    private val scheduler = RecordingScheduler()
    private val queue = CheckInQueue(repository, dao, clock = { NOW }, scheduler = scheduler)

    @Test
    fun `a scan that cannot reach the server is held`() = runTest {
        repository.nextResult = offline()

        val result = queue.scan(SESSION, CODE, installId = "install-1")

        assertEquals(CheckInResult.Queued, result)
        assertEquals(1, dao.rows.size)
        assertEquals(CODE, dao.rows.single().code)
        // The device's clock, captured now. By the time this is sent the
        // server's will say something else entirely.
        assertEquals(NOW, dao.rows.single().checkedInAtEpochSeconds)
    }

    @Test
    fun `buffering asks the platform to drain later`() = runTest {
        repository.nextResult = offline()

        queue.scan(SESSION, CODE, installId = null)

        // Without this the queue only drains when someone opens the scanner,
        // and a supervisor who pockets the phone takes the evening with them.
        assertEquals(1, scheduler.scheduled)
    }

    @Test
    fun `nothing is scheduled when the check-in got through`() = runTest {
        queue.scan(SESSION, CODE, installId = null)

        assertEquals(0, scheduler.scheduled)
    }

    @Test
    fun `emptiness is what the worker asks about`() = runTest {
        assertTrue(queue.isEmpty())

        repository.nextResult = offline()
        queue.scan(SESSION, CODE, installId = null)

        assertTrue(!queue.isEmpty())
    }

    @Test
    fun `a refused scan is not held`() = runTest {
        // Retrying an expired code later cannot change the answer, and a queue
        // that never drains is worse than an error.
        repository.nextResult = ApiResult.Failure(ApiError.Http(422, "VALIDATION_ERROR", null))

        val result = queue.scan(SESSION, CODE, installId = null)

        assertTrue(result is CheckInResult.Rejected)
        assertTrue(dao.rows.isEmpty())
    }

    @Test
    fun `a successful scan is not held`() = runTest {
        val result = queue.scan(SESSION, CODE, installId = null)

        assertTrue(result is CheckInResult.Recorded)
        assertTrue(dao.rows.isEmpty())
    }

    @Test
    fun `a manual check-in that cannot reach the server is held with the name`() = runTest {
        repository.nextResult = offline()

        queue.checkInManually(SESSION, MEMBER, installId = null)

        val row = dao.rows.single()
        assertEquals(MEMBER.id, row.memberId)
        // Kept so the supervisor can be shown what is still waiting without a
        // lookup they may have no connection to make.
        assertEquals(MEMBER.name, row.memberLabel)
        assertNull(row.code)
    }

    /**
     * The regression test for the duplicate guest. The server deduplicates
     * check-ins by a client-assigned id — but only if every retry of the same
     * queued row sends the *same* id. A fresh id per attempt would make the
     * mechanism decorative.
     */
    @Test
    fun `a retried drain sends the same client id every time`() = runTest {
        repository.nextResult = offline()
        queue.checkInGuest(SESSION, "Jonas Gast", installId = null)

        repository.nextResult = offline()
        queue.sync()
        repository.nextResult = null
        queue.sync()

        // Three sends: the live attempt, the offline drain, the successful
        // drain — one id across all of them.
        val sent = repository.sentClientIds
        assertEquals(3, sent.size)
        assertNotNull(sent[0])
        assertEquals(1, sent.toSet().size)
        assertTrue(dao.rows.isEmpty())
    }

    @Test
    fun `a guest who cannot be sent is held under their name`() = runTest {
        repository.nextResult = offline()

        queue.checkInGuest(SESSION, "Jonas Gast", installId = null)

        val row = dao.rows.single()
        assertEquals("Jonas Gast", row.guestName)
        assertNull(row.memberId)
        assertNull(row.code)
        // Shown to the supervisor while it waits, without a lookup they may
        // have no connection to make.
        assertEquals("Jonas Gast", row.memberLabel)
    }

    @Test
    fun `a queued guest is sent as a guest, not as a member`() = runTest {
        repository.nextResult = offline()
        queue.checkInGuest(SESSION, "Jonas Gast", installId = null)
        repository.nextResult = null

        assertEquals(1, queue.sync())

        assertEquals("Jonas Gast", repository.lastGuestName)
        assertTrue(dao.rows.isEmpty())
    }

    @Test
    fun `syncing sends the device time, not now`() = runTest {
        repository.nextResult = offline()
        queue.scan(SESSION, CODE, installId = null)
        repository.nextResult = null

        assertEquals(1, queue.sync())

        // 2026-07-07T18:00:00Z — the moment it was taken, which is the only
        // record of when the person was actually there.
        assertEquals("2026-07-07T18:00:00Z", repository.lastCheckedInAt)
        assertTrue(dao.rows.isEmpty())
    }

    @Test
    fun `syncing stops at the first connection failure`() = runTest {
        repository.nextResult = offline()
        queue.scan(SESSION, "$CODE-1", installId = null)
        queue.scan(SESSION, "$CODE-2", installId = null)
        queue.scan(SESSION, "$CODE-3", installId = null)

        // Counting only the drain: each scan above already tried the network
        // once on its way into the queue.
        repository.calls = 0

        // Still offline: hammering a dead connection only delays the screen, so
        // one refusal ends the pass and the other two rows stay untouched.
        assertEquals(0, queue.sync())
        assertEquals(3, dao.rows.size)
        assertEquals(1, repository.calls)
    }

    @Test
    fun `a row the server says is already checked in is done`() = runTest {
        repository.nextResult = offline()
        queue.scan(SESSION, CODE, installId = null)
        repository.nextResult = ApiResult.Failure(ApiError.Http(409, "ALREADY_CHECKED_IN", null))

        queue.sync()

        // The person is in, however they got there, so the row has no work left.
        assertTrue(dao.rows.isEmpty())
    }

    @Test
    fun `a row the server refuses is kept and marked`() = runTest {
        repository.nextResult = offline()
        queue.scan(SESSION, CODE, installId = null)
        repository.nextResult = ApiResult.Failure(ApiError.Http(422, "VALIDATION_ERROR", null))

        queue.sync()

        // Dropping it is the one outcome nobody could notice: the check-in
        // happened, and no other record of it exists.
        assertEquals(1, dao.rows.size)
        assertEquals(1, dao.rows.single().attempts)
        assertEquals("VALIDATION_ERROR", dao.rows.single().lastError)
    }

    @Test
    fun `the oldest check-in drains first`() = runTest {
        repository.nextResult = offline()
        dao.insert(pending(id = 0, code = "later", at = NOW + 100))
        dao.insert(pending(id = 0, code = "earlier", at = NOW))
        repository.nextResult = null

        queue.sync()

        assertEquals(listOf("earlier", "later"), repository.sentCodes)
    }

    private fun offline() = ApiResult.Failure(ApiError.Network(IOException("no route to host")))

    private fun pending(id: Long, code: String, at: Long) =
        PendingCheckIn(id = id, sessionId = SESSION, code = code, checkedInAtEpochSeconds = at)

    private companion object {
        const val SESSION = "session-1"
        const val CODE = "uf1.AAAAAAAAAAAAAAAA.59448240.VW54OV2ZM3OO4N6X"

        /** 2026-07-07T18:00:00Z. */
        const val NOW = 1_783_447_200L

        val MEMBER = MemberPick(id = "member-1", memberNumber = "TV-001", name = "Alice Example")
    }
}

/** In-memory stand-in for Room. The queue's rules are about ordering and
 *  lifecycle, neither of which needs a real database to exercise. */
private class FakeDao : PendingCheckInDao {
    val rows = mutableListOf<PendingCheckIn>()
    private var nextId = 1L
    private val count = MutableStateFlow(0)

    override suspend fun insert(entry: PendingCheckIn): Long {
        val id = nextId++
        rows += entry.copy(id = id)
        count.value = rows.size
        return id
    }

    override suspend fun all(): List<PendingCheckIn> = rows.sortedBy { it.checkedInAtEpochSeconds }

    override fun countStream(): Flow<Int> = count

    override suspend fun forSession(sessionId: String): List<PendingCheckIn> =
        rows.filter { it.sessionId == sessionId }

    override suspend fun delete(id: Long) {
        rows.removeAll { it.id == id }
        count.value = rows.size
    }

    override suspend fun recordFailure(id: Long, error: String?) {
        val index = rows.indexOfFirst { it.id == id }
        if (index >= 0) {
            rows[index] = rows[index].copy(attempts = rows[index].attempts + 1, lastError = error)
        }
    }
}

private class RecordingScheduler : SyncScheduler {
    var scheduled = 0

    override fun scheduleDrain() {
        scheduled++
    }
}

private class FakeRepository : AttendanceRepository {
    /** Null means succeed. */
    var nextResult: ApiResult<ScanOutcome>? = null
    var lastCheckedInAt: String? = null
    var lastGuestName: String? = null
    var calls = 0
    val sentCodes = mutableListOf<String>()

    private val success = ApiResult.Success(ScanOutcome("Alice Example", "TV-001", "high"))

    override suspend fun scan(
        sessionId: String,
        code: String,
        installId: String?,
        staffDeviceId: String?,
        checkedInAt: String?,
    ): ApiResult<ScanOutcome> {
        calls++
        lastCheckedInAt = checkedInAt
        sentCodes += code
        return nextResult ?: success
    }

    override suspend fun checkInManually(
        sessionId: String,
        memberId: String?,
        guestName: String?,
        checkedInAt: String?,
        clientId: String?,
    ): ApiResult<ScanOutcome> {
        calls++
        lastCheckedInAt = checkedInAt
        lastGuestName = guestName
        sentClientIds += clientId
        return nextResult ?: success
    }

    val sentClientIds = mutableListOf<String?>()

    override suspend fun createSession(
        title: String,
        opensAt: String,
        closesAt: String,
    ): ApiResult<AttendanceSessionSummary> = error("not used")

    override suspend fun seed(): ApiResult<AttendanceSeed> = error("not used")

    override suspend fun openSessions(): ApiResult<List<AttendanceSessionSummary>> =
        error("not used")

    override suspend fun members(search: String?): ApiResult<List<MemberPick>> = error("not used")

    override suspend fun sessionRecords(sessionId: String): ApiResult<List<CheckedInEntry>> =
        error("not used")

    override suspend fun latestOwnCheckIn(): ApiResult<OwnCheckIn?> = error("not used")

    override suspend fun deleteRecord(recordId: String, reason: String?): ApiResult<Unit> =
        error("not used")

    override suspend fun myRangeDays() = error("not used")

    override suspend fun createSelfEntry(occurredOn: String, location: String) = error("not used")

    override suspend fun deleteSelfEntry(recordId: String) = error("not used")

    override suspend fun todaysEvents(startIso: String, endIso: String) = error("not used")

    override suspend fun openSessionForEvent(eventId: String) = error("not used")
}
