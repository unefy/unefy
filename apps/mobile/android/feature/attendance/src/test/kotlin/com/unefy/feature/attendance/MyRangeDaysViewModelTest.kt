package com.unefy.feature.attendance

import com.unefy.core.auth.ClubRepository
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
 * The member's own range history: both origins in one list, the self-entry
 * form, and the refusals that must arrive as words rather than silence.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class MyRangeDaysViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    private val repository = FakeRangeDaysRepository()
    private val shootingDetails = FakeRangeShootingDetails()

    private fun viewModel(modules: List<String> = listOf("shooting")) = MyRangeDaysViewModel(
        repository = repository,
        clubRepository = clubRepository(modules),
        shootingDetails = shootingDetails,
        clock = AttendanceClock { 1_754_400_000 },
    )

    private fun clubRepository(modules: List<String>): ClubRepository {
        val moduleJson = modules.joinToString(",") { "\"$it\"" }
        val engine = MockEngine.create {
            dispatcher = this@MyRangeDaysViewModelTest.dispatcher
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
    fun `club evenings and own entries arrive as one list`() = runTest(dispatcher) {
        repository.days = listOf(
            OwnRangeDay("r1", "2026-08-04", "Übungsabend", null, "club", "staff_scan"),
            OwnRangeDay("r2", "2026-08-02", null, "SV Nachbarort", "external", "self"),
        )

        val viewModel = viewModel()
        runCurrent()

        assertEquals(listOf("club", "external"), viewModel.uiState.value.days.map { it.origin })
        assertTrue(viewModel.uiState.value.shooting != null)
    }

    @Test
    fun `a club without the module gets no shooting fields`() = runTest(dispatcher) {
        val viewModel = viewModel(modules = emptyList())
        runCurrent()

        assertNull(viewModel.uiState.value.shooting)
    }

    @Test
    fun `saving writes the entry and its detail`() = runTest(dispatcher) {
        val viewModel = viewModel()
        runCurrent()

        viewModel.openForm()
        viewModel.save("SV Nachbarort", "c1", "luftdruck", 40)
        runCurrent()

        assertEquals("SV Nachbarort", repository.created.single().second)
        assertEquals(40, shootingDetails.saved.single().roundsFired)
        assertNull(viewModel.uiState.value.form)
        assertEquals(RangeDaysNotice.Created, viewModel.uiState.value.notice)
    }

    @Test
    fun `without the module no detail call is made`() = runTest(dispatcher) {
        val viewModel = viewModel(modules = emptyList())
        runCurrent()

        viewModel.openForm()
        viewModel.save("SV Nachbarort", null, null, 40)
        runCurrent()

        assertEquals(1, repository.created.size)
        assertTrue(shootingDetails.saved.isEmpty())
    }

    @Test
    fun `a failed save keeps the form open`() = runTest(dispatcher) {
        repository.createResult =
            ApiResult.Failure(ApiError.Network(java.io.IOException()))

        val viewModel = viewModel()
        runCurrent()
        viewModel.openForm()
        viewModel.save("SV Nachbarort", null, null, null)
        runCurrent()

        val state = viewModel.uiState.value
        assertTrue(state.form != null && !state.form!!.saving)
        assertTrue(state.notice is RangeDaysNotice.Failed)
    }

    @Test
    fun `a second entry for the same day closes the form and says why`() = runTest(dispatcher) {
        repository.createResult = ApiResult.Failure(
            ApiError.Http(status = 409, code = "SELF_ENTRY_EXISTS", message = null),
        )

        val viewModel = viewModel()
        runCurrent()
        viewModel.openForm()
        viewModel.save("SV Nachbarort", null, null, null)
        runCurrent()

        assertNull(viewModel.uiState.value.form)
        assertEquals(RangeDaysNotice.DayTaken, viewModel.uiState.value.notice)
    }

    @Test
    fun `club rows cannot be deleted`() = runTest(dispatcher) {
        val club = OwnRangeDay("r1", "2026-08-04", "Übungsabend", null, "club", "staff_scan")
        repository.days = listOf(club)

        val viewModel = viewModel()
        runCurrent()
        viewModel.delete(club)
        runCurrent()

        assertTrue(repository.deleted.isEmpty())
    }

    @Test
    fun `a certified entry refuses deletion with its own words`() = runTest(dispatcher) {
        val external = OwnRangeDay("r2", "2026-08-02", null, "SV Nachbarort", "external", "self")
        repository.days = listOf(external)
        repository.deleteResult = ApiResult.Failure(
            ApiError.Http(status = 409, code = "RECORD_CERTIFIED", message = null),
        )

        val viewModel = viewModel()
        runCurrent()
        viewModel.delete(external)
        runCurrent()

        assertEquals(RangeDaysNotice.Certified, viewModel.uiState.value.notice)
        // The list is reloaded so the swiped row comes back.
        assertEquals(listOf("r2"), viewModel.uiState.value.days.map { it.id })
    }
}

private class FakeRangeDaysRepository : AttendanceRepository {
    var days: List<OwnRangeDay> = emptyList()
    var createResult: ApiResult<OwnRangeDay>? = null
    var deleteResult: ApiResult<Unit>? = null

    val created = mutableListOf<Pair<String, String>>()
    val deleted = mutableListOf<String>()

    override suspend fun myRangeDays(): ApiResult<List<OwnRangeDay>> = ApiResult.Success(days)

    override suspend fun createSelfEntry(
        occurredOn: String,
        location: String,
    ): ApiResult<OwnRangeDay> {
        createResult?.let { return it }
        created += occurredOn to location
        val day = OwnRangeDay("new-${created.size}", occurredOn, null, location, "external", "self")
        days = listOf(day) + days
        return ApiResult.Success(day)
    }

    override suspend fun deleteSelfEntry(recordId: String): ApiResult<Unit> {
        deleteResult?.let { return it }
        deleted += recordId
        days = days.filterNot { it.id == recordId }
        return ApiResult.Success(Unit)
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

    override suspend fun todaysEvents(startIso: String, endIso: String) = error("unused")

    override suspend fun openSessionForEvent(eventId: String) = error("unused")

    override suspend fun members(search: String?) = error("unused")

    override suspend fun sessionRecords(sessionId: String) = error("unused")

    override suspend fun latestOwnCheckIn() = error("unused")

    override suspend fun deleteRecord(recordId: String, reason: String?) = error("unused")
}

private class FakeRangeShootingDetails : ShootingDetailRepository {
    val saved = mutableListOf<ShootingDetail>()

    override suspend fun forSession(sessionId: String): ApiResult<Map<String, ShootingDetail>> =
        ApiResult.Success(emptyMap())

    override suspend fun disciplines(): ApiResult<List<ClubDiscipline>> =
        ApiResult.Success(listOf(ClubDiscipline("c1", "Luftgewehr", "LG 10m")))

    override suspend fun save(
        recordId: String,
        clubDisciplineId: String?,
        weaponCategory: String?,
        roundsFired: Int?,
    ): ApiResult<ShootingDetail> {
        val detail = ShootingDetail(recordId, clubDisciplineId, weaponCategory, roundsFired)
        saved += detail
        return ApiResult.Success(detail)
    }
}
