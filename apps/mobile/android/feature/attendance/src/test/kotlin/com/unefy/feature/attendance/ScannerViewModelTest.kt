package com.unefy.feature.attendance

import com.unefy.core.database.PendingCheckIn
import com.unefy.core.database.PendingCheckInDao
import com.unefy.core.network.ApiResult
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * What the scanner claims about itself while it is fetching.
 *
 * This screen reloads on every resume, and at a range the reload is the slowest
 * thing it does — a dead connection answers only when it times out. What the
 * screen shows during those seconds is the whole difference between a scanner
 * and a blank page.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class ScannerViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    private fun viewModel(repository: FakeRepository) = ScannerViewModel(
        repository = repository,
        queue = CheckInQueue(repository, FakeDao(), clock = { NOW }),
        deviceIdentity = object : DeviceIdentity {
            override suspend fun installId() = "install-1"
        },
        clock = { NOW },
    )

    /**
     * Regression: a refresh used to flip the screen back to "loading", and the
     * viewfinder lived inside that branch — so every resume tore the camera
     * down and bound it again. Offline, where the reload runs for the whole
     * timeout, the scanner had no scanner on it at all, which is how it was
     * reported.
     */
    @Test
    fun `a refresh does not take the screen back to loading`() = runTest(dispatcher) {
        val repository = FakeRepository()
        val viewModel = viewModel(repository)
        runCurrent()
        assertFalse(viewModel.uiState.value.loadingSessions)
        assertEquals(1, viewModel.uiState.value.sessions.size)

        // A load that does not answer — the offline case, until the timeout.
        repository.hold = CompletableDeferred()
        viewModel.refresh()
        runCurrent()

        assertFalse(viewModel.uiState.value.loadingSessions)
        assertEquals(1, viewModel.uiState.value.sessions.size)
        assertEquals(SESSION, viewModel.uiState.value.selectedSessionId)
    }

    /** The first load has nothing to keep, so it may still say so. */
    @Test
    fun `the very first load does say it is loading`() = runTest(dispatcher) {
        val repository = FakeRepository().apply { hold = CompletableDeferred() }
        val viewModel = viewModel(repository)
        runCurrent()

        assertTrue(viewModel.uiState.value.loadingSessions)
    }

    private companion object {
        const val SESSION = "session-1"

        /** 2026-07-07T18:00:00Z. */
        const val NOW = 1_783_447_200L
    }
}

private class FakeRepository : AttendanceRepository {
    /** Non-null makes the next load hang, the way a dead connection does. */
    var hold: CompletableDeferred<Unit>? = null

    override suspend fun openSessions(): ApiResult<List<AttendanceSessionSummary>> {
        hold?.await()
        return ApiResult.Success(
            listOf(AttendanceSessionSummary("session-1", "Übungsabend", null, recordCount = 0)),
        )
    }

    override suspend fun sessionRecords(sessionId: String): ApiResult<List<CheckedInEntry>> =
        ApiResult.Success(emptyList())

    override suspend fun scan(
        sessionId: String,
        code: String,
        installId: String?,
        staffDeviceId: String?,
        checkedInAt: String?,
    ) = error("not used")

    override suspend fun checkInManually(
        sessionId: String,
        memberId: String?,
        guestName: String?,
        checkedInAt: String?,
        clientId: String?,
    ) = error("not used")

    override suspend fun createSession(title: String, opensAt: String, closesAt: String) =
        error("not used")

    override suspend fun seed() = error("not used")

    override suspend fun members(search: String?) = error("not used")

    override suspend fun latestOwnCheckIn() = error("not used")

    override suspend fun deleteRecord(recordId: String, reason: String?) = error("not used")

    override suspend fun myRangeDays() = error("not used")

    override suspend fun createSelfEntry(occurredOn: String, location: String) = error("not used")

    override suspend fun deleteSelfEntry(recordId: String) = error("not used")

    override suspend fun todaysEvents(startIso: String, endIso: String) = error("not used")

    override suspend fun openSessionForEvent(eventId: String) = error("not used")
}

private class FakeDao : PendingCheckInDao {
    private val rows = mutableListOf<PendingCheckIn>()
    private val count = MutableStateFlow(0)

    override suspend fun insert(entry: PendingCheckIn): Long = 1L

    override suspend fun all(): List<PendingCheckIn> = rows

    override fun countStream(): Flow<Int> = count

    override suspend fun forSession(sessionId: String): List<PendingCheckIn> = rows

    override suspend fun delete(id: Long) = Unit

    override suspend fun recordFailure(id: Long, error: String?) = Unit
}
