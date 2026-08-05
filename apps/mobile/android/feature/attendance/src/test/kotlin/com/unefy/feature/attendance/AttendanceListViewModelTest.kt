package com.unefy.feature.attendance

import com.unefy.core.auth.ClubRepository
import com.unefy.core.database.PendingCheckIn
import com.unefy.core.database.PendingCheckInDao
import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.respond
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.http.ContentType
import io.ktor.http.HttpStatusCode
import io.ktor.http.headersOf
import io.ktor.serialization.kotlinx.json.json
import io.ktor.utils.io.ByteReadChannel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.serialization.json.Json
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * The attendance list as its own screen: the merge of recorded and buffered
 * check-ins, the shooting column that only exists for a club that shoots, and
 * the undo/save aftermath the notices carry.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class AttendanceListViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    private val dao = FakeListDao()
    private val repository = FakeListRepository()
    private val shootingDetails = FakeShootingDetailRepository()

    private fun viewModel(modules: List<String> = emptyList()) = AttendanceListViewModel(
        repository = repository,
        queue = CheckInQueue(repository, dao, clock = AttendanceClock { 0 }),
        clubRepository = clubRepository(modules),
        shootingDetails = shootingDetails,
    )

    /** The real repository over a canned club — the class is not an interface. */
    private fun clubRepository(modules: List<String>): ClubRepository {
        val moduleJson = modules.joinToString(",") { "\"$it\"" }
        val engine = MockEngine.create {
            // On the test scheduler, not MockEngine's own thread pool — the
            // probe has to finish inside runCurrent() or every assertion races.
            dispatcher = this@AttendanceListViewModelTest.dispatcher
            addHandler {
                respond(
                    content = ByteReadChannel(
                        """{"data": {"id": "club-1", "name": "TV", "modules": [$moduleJson]}}""",
                    ),
                    status = HttpStatusCode.OK,
                    headers = headersOf("Content-Type", ContentType.Application.Json.toString()),
                )
            }
        }
        val client = HttpClient(engine) {
            install(ContentNegotiation) { json(Json { ignoreUnknownKeys = true }) }
        }
        return ClubRepository(ApiClient(client))
    }

    @Test
    fun `recorded and buffered check-ins arrive as one list, newest first`() = runTest(dispatcher) {
        repository.records = listOf(
            entry("r1", at = 100),
            entry("r2", at = 300),
        )
        dao.insert(pending(sessionId = "s1", label = "Queued Quentin", at = 200))
        // Another session's buffer stays out of this session's list.
        dao.insert(pending(sessionId = "other", label = "Elsewhere Emil", at = 250))

        val viewModel = viewModel()
        viewModel.load("s1")
        runCurrent()

        val entries = viewModel.uiState.value.entries
        assertEquals(listOf("r2", "pending-1", "r1"), entries.map { it.key })
        assertEquals(listOf(false, true, false), entries.map { it.pending })
    }

    @Test
    fun `a club without the shooting module gets no shooting column`() = runTest(dispatcher) {
        val viewModel = viewModel(modules = emptyList())
        viewModel.load("s1")
        runCurrent()

        assertNull(viewModel.uiState.value.shooting)
    }

    @Test
    fun `a shooting club gets disciplines and the session's details`() = runTest(dispatcher) {
        repository.records = listOf(entry("r1", at = 100))
        shootingDetails.details = mapOf("r1" to ShootingDetail("r1", "c1", "luftdruck", 40))

        val viewModel = viewModel(modules = listOf("shooting"))
        viewModel.load("s1")
        runCurrent()

        val shooting = viewModel.uiState.value.shooting
        assertEquals(listOf("c1"), shooting?.disciplines?.map { it.id })
        assertEquals(40, shooting?.details?.get("r1")?.roundsFired)
    }

    @Test
    fun `undoing a buffered check-in drops it from the queue`() = runTest(dispatcher) {
        dao.insert(pending(sessionId = "s1", label = "Queued Quentin", at = 200))

        val viewModel = viewModel()
        viewModel.load("s1")
        runCurrent()
        val queuedRow = viewModel.uiState.value.entries.single()

        viewModel.undo(queuedRow)
        runCurrent()

        assertTrue(dao.rows.isEmpty())
        assertTrue(viewModel.uiState.value.entries.isEmpty())
        assertEquals(
            AttendanceListNotice.Undone("Queued Quentin"),
            viewModel.uiState.value.notice,
        )
    }

    @Test
    fun `a refused undo keeps the row and says so`() = runTest(dispatcher) {
        repository.records = listOf(entry("r1", at = 100))
        repository.deleteResult = ApiResult.Failure(ApiError.Http(status = 409, code = "SESSION_CLOSED", message = null))

        val viewModel = viewModel()
        viewModel.load("s1")
        runCurrent()

        viewModel.undo(viewModel.uiState.value.entries.single())
        runCurrent()

        assertEquals(listOf("r1"), viewModel.uiState.value.entries.map { it.key })
        assertTrue(viewModel.uiState.value.notice is AttendanceListNotice.UndoFailed)
    }

    @Test
    fun `a saved detail takes the server's answer and closes the sheet`() = runTest(dispatcher) {
        repository.records = listOf(entry("r1", at = 100))
        shootingDetails.saveResult =
            ApiResult.Success(ShootingDetail("r1", "c1", "kurzwaffe", 60))

        val viewModel = viewModel(modules = listOf("shooting"))
        viewModel.load("s1")
        runCurrent()

        viewModel.editShootingDetail(viewModel.uiState.value.entries.single())
        viewModel.saveShootingDetail("c1", "kurzwaffe", 99)
        runCurrent()

        val shooting = viewModel.uiState.value.shooting
        assertNull(shooting?.editing)
        // 60, not the typed 99: the server is what the range book will print.
        assertEquals(60, shooting?.details?.get("r1")?.roundsFired)
    }

    @Test
    fun `a failed save keeps the sheet open with a notice`() = runTest(dispatcher) {
        repository.records = listOf(entry("r1", at = 100))
        shootingDetails.saveResult = ApiResult.Failure(ApiError.Network(java.io.IOException()))

        val viewModel = viewModel(modules = listOf("shooting"))
        viewModel.load("s1")
        runCurrent()

        viewModel.editShootingDetail(viewModel.uiState.value.entries.single())
        viewModel.saveShootingDetail("c1", null, null)
        runCurrent()

        val state = viewModel.uiState.value
        assertEquals("r1", state.shooting?.editing?.key)
        assertTrue(state.notice is AttendanceListNotice.SaveFailed)
    }

    @Test
    fun `a failed read is only an error while there is nothing to show`() = runTest(dispatcher) {
        repository.recordsResult =
            ApiResult.Failure(ApiError.Http(status = 500, code = "INTERNAL", message = null))

        val viewModel = viewModel()
        viewModel.load("s1")
        runCurrent()
        assertTrue(viewModel.uiState.value.error != null)

        // Once the list has content, a tripped reload must not replace it.
        repository.recordsResult = null
        repository.records = listOf(entry("r1", at = 100))
        viewModel.refresh()
        runCurrent()
        assertNull(viewModel.uiState.value.error)

        repository.recordsResult =
            ApiResult.Failure(ApiError.Http(status = 500, code = "INTERNAL", message = null))
        viewModel.refresh()
        runCurrent()

        assertNull(viewModel.uiState.value.error)
        assertEquals(listOf("r1"), viewModel.uiState.value.entries.map { it.key })
    }

    private fun entry(key: String, at: Long) = CheckedInEntry(
        key = key,
        memberId = "member-$key",
        memberName = "Member $key",
        method = "staff_scan",
        checkedInAtEpochSeconds = at,
    )

    private fun pending(sessionId: String, label: String, at: Long) = PendingCheckIn(
        sessionId = sessionId,
        memberId = "member-$label",
        memberLabel = label,
        checkedInAtEpochSeconds = at,
    )
}

/** In-memory stand-in for Room, matching the one in CheckInQueueTest. */
private class FakeListDao : PendingCheckInDao {
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

private class FakeListRepository : AttendanceRepository {
    var records: List<CheckedInEntry> = emptyList()

    /** Non-null forces the next read to fail. */
    var recordsResult: ApiResult<List<CheckedInEntry>>? = null

    /** Null means succeed. */
    var deleteResult: ApiResult<Unit>? = null

    override suspend fun sessionRecords(sessionId: String): ApiResult<List<CheckedInEntry>> =
        recordsResult ?: ApiResult.Success(records)

    override suspend fun deleteRecord(recordId: String, reason: String?): ApiResult<Unit> {
        val result = deleteResult ?: ApiResult.Success(Unit)
        if (result is ApiResult.Success) records = records.filterNot { it.key == recordId }
        return result
    }

    override suspend fun seed() = error("unused")

    override suspend fun openSessions() = error("unused")

    override suspend fun scan(
        sessionId: String,
        code: String,
        installId: String?,
        staffDeviceId: String?,
        checkedInAt: String?,
    ) = error("unused")

    override suspend fun checkInManually(
        sessionId: String,
        memberId: String?,
        guestName: String?,
        checkedInAt: String?,
        clientId: String?,
    ) = error("unused")

    override suspend fun createSession(title: String, opensAt: String, closesAt: String) =
        error("unused")

    override suspend fun members(search: String?) = error("unused")

    override suspend fun latestOwnCheckIn() = error("unused")

    override suspend fun myRangeDays() = error("unused")

    override suspend fun createSelfEntry(occurredOn: String, location: String) = error("unused")

    override suspend fun deleteSelfEntry(recordId: String) = error("unused")

    override suspend fun todaysEvents(startIso: String, endIso: String) = error("unused")

    override suspend fun openSessionForEvent(eventId: String) = error("unused")
}

private class FakeShootingDetailRepository : ShootingDetailRepository {
    var details: Map<String, ShootingDetail> = emptyMap()
    var saveResult: ApiResult<ShootingDetail>? = null

    override suspend fun forSession(sessionId: String): ApiResult<Map<String, ShootingDetail>> =
        ApiResult.Success(details)

    override suspend fun disciplines(): ApiResult<List<ClubDiscipline>> =
        ApiResult.Success(listOf(ClubDiscipline("c1", "Luftgewehr", "LG 10m")))

    override suspend fun save(
        recordId: String,
        clubDisciplineId: String?,
        weaponCategory: String?,
        roundsFired: Int?,
    ): ApiResult<ShootingDetail> {
        val result = saveResult ?: error("saveResult not set")
        if (result is ApiResult.Success) details = details + (recordId to result.data)
        return result
    }
}
