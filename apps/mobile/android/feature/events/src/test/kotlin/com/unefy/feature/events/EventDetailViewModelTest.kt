package com.unefy.feature.events

import com.unefy.core.model.Event
import com.unefy.core.model.EventDetail
import com.unefy.core.model.EventRegistration
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import com.unefy.core.sync.ConnectivityMonitor
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * The event detail merges the mirrored row with the single-event fetch. These
 * tests pin the merge direction (mirror wins for its fields, the fetch only
 * enriches), the offline degradation, and the toggle that must hold the
 * confirmed state even when the re-fetch after it fails.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class EventDetailViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `a mirrored event shows before the fetch answers`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(mirror = listOf(event("e")))
        repository.detailFailure = ApiError.Network(IOException("offline"))
        val viewModel = viewModel(repository)
        viewModel.load("e")
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventDetailUiState.Content
        assertEquals("e", state.event.id)
        assertFalse(state.detailLoaded)
        assertTrue(state.registrations.isEmpty())
    }

    @Test
    fun `the fetch enriches the mirrored row and brings the participants`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(mirror = listOf(event("e")))
        repository.details["e"] = EventDetail(
            event = event("e").copy(
                isRegistered = true,
                registeredCount = 7,
                competitionName = "Königsschießen",
                // The fetched copy must NOT win for mirror-owned fields.
                title = "Veralteter Titel",
            ),
            registrations = listOf(registration("r1", "Susanne Bauer")),
        )
        val viewModel = viewModel(repository)
        viewModel.load("e")
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventDetailUiState.Content
        assertTrue(state.detailLoaded)
        assertTrue(state.event.isRegistered)
        assertEquals(7, state.event.registeredCount)
        assertEquals("Königsschießen", state.event.competitionName)
        assertEquals("Termin e", state.event.title)
        assertEquals(listOf("Susanne Bauer"), state.registrations.map { it.memberName })
    }

    /** An event the mirror does not carry still opens — from the fetch alone. */
    @Test
    fun `an unmirrored event renders from the fetch`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(mirror = emptyList())
        repository.details["e"] = EventDetail(event("e"), emptyList())
        val viewModel = viewModel(repository)
        viewModel.load("e")
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventDetailUiState.Content
        assertEquals("e", state.event.id)
        assertTrue(state.detailLoaded)
    }

    @Test
    fun `nothing mirrored and a failed fetch is a Failure`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(mirror = emptyList())
        repository.detailFailure = ApiError.Network(IOException("offline"))
        val viewModel = viewModel(repository)
        viewModel.load("e")
        advanceUntilIdle()

        assertTrue(viewModel.uiState.value is EventDetailUiState.Failure)
    }

    @Test
    fun `registering re-fetches so the participant list shows the new world`() =
        runTest(dispatcher) {
            val repository = FakeDetailRepository(mirror = listOf(event("e")))
            repository.details["e"] = EventDetail(
                event("e").copy(registeredCount = 5),
                emptyList(),
            )
            val viewModel = viewModel(repository)
            viewModel.load("e")
            advanceUntilIdle()

            repository.details["e"] = EventDetail(
                event("e").copy(isRegistered = true, registeredCount = 6),
                listOf(registration("r9", "Ich Selbst")),
            )
            viewModel.toggleRegistration()
            advanceUntilIdle()

            assertTrue(repository.registered.contains("e"))
            val state = viewModel.uiState.value as EventDetailUiState.Content
            assertTrue(state.event.isRegistered)
            assertEquals(6, state.event.registeredCount)
            assertEquals(listOf("Ich Selbst"), state.registrations.map { it.memberName })
            assertFalse(state.busy)
        }

    /**
     * The regression case: the toggle succeeded but the re-fetch died. The
     * button must hold the acknowledged state, not invite a second, doomed tap.
     */
    @Test
    fun `a confirmed toggle survives a failed re-fetch`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(mirror = listOf(event("e")))
        repository.details["e"] = EventDetail(
            event("e").copy(isRegistered = false, registeredCount = 5),
            emptyList(),
        )
        val viewModel = viewModel(repository)
        viewModel.load("e")
        advanceUntilIdle()

        repository.detailFailure = ApiError.Network(IOException("gone mid-toggle"))
        viewModel.toggleRegistration()
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventDetailUiState.Content
        assertTrue(state.event.isRegistered)
        assertEquals(6, state.event.registeredCount)
    }

    /** Registering into a full event waitlists — the pill must not claim +1. */
    @Test
    fun `registering into a full event does not inflate the count`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(mirror = listOf(event("e")))
        repository.details["e"] = EventDetail(
            event("e").copy(registeredCount = 40),
            emptyList(),
        )
        val viewModel = viewModel(repository)
        viewModel.load("e")
        advanceUntilIdle()

        // The re-fetch dies, so the optimistic value is what the screen keeps.
        repository.detailFailure = ApiError.Network(IOException("gone mid-toggle"))
        viewModel.toggleRegistration()
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventDetailUiState.Content
        assertTrue(state.event.isRegistered)
        assertEquals(40, state.event.registeredCount)
    }

    @Test
    fun `a failed toggle changes nothing and releases the lock`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(mirror = listOf(event("e")))
        repository.details["e"] = EventDetail(
            event("e").copy(registeredCount = 5),
            emptyList(),
        )
        val viewModel = viewModel(repository)
        viewModel.load("e")
        advanceUntilIdle()

        repository.actionFailure = ApiError.Forbidden
        viewModel.toggleRegistration()
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventDetailUiState.Content
        assertFalse(state.event.isRegistered)
        assertEquals(5, state.event.registeredCount)
        assertFalse(state.busy)
        assertTrue(repository.registered.isEmpty())
    }

    /** Before the fetch answers there is nothing to toggle against — no blind write. */
    @Test
    fun `toggling before the detail loaded is a no-op`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(mirror = listOf(event("e")))
        repository.detailFailure = ApiError.Network(IOException("offline"))
        val viewModel = viewModel(repository)
        viewModel.load("e")
        advanceUntilIdle()

        viewModel.toggleRegistration()
        advanceUntilIdle()

        assertTrue(repository.registered.isEmpty())
    }

    @Test
    fun `a mirror update while the screen is open lands in the state`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(mirror = listOf(event("e")))
        repository.details["e"] = EventDetail(event("e"), emptyList())
        val viewModel = viewModel(repository)
        viewModel.load("e")
        advanceUntilIdle()

        repository.mirror.value = listOf(event("e").copy(title = "Neuer Titel"))
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventDetailUiState.Content
        assertEquals("Neuer Titel", state.event.title)
    }

    // ------------------------------------------------------------------
    // Board actions
    // ------------------------------------------------------------------

    @Test
    fun `the picker loads options and registering adds the member`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(mirror = listOf(event("e")))
        repository.details["e"] = EventDetail(
            event("e").copy(registeredCount = 5),
            emptyList(),
        )
        repository.options += MemberOption("m9", "TV-009", "Petra Meyer")
        val viewModel = viewModel(repository)
        viewModel.load("e")
        advanceUntilIdle()

        viewModel.openPicker()
        advanceUntilIdle()
        assertEquals(listOf("Petra Meyer"), viewModel.picker.value.options.map { it.name })

        // The re-fetch dies, so the local confirmed row is what the screen keeps.
        repository.detailFailure = ApiError.Network(IOException("gone"))
        viewModel.pickMember(repository.options.single())
        advanceUntilIdle()

        assertTrue("m9" in repository.boardRegistered)
        val state = viewModel.uiState.value as EventDetailUiState.Content
        assertEquals(listOf("Petra Meyer"), state.registrations.map { it.memberName })
        assertEquals(6, state.event.registeredCount)
        assertEquals(null, viewModel.picker.value.pendingMemberId)
    }

    /** A full event waitlists the added member — locally too, count untouched. */
    @Test
    fun `registering into a full event waitlists the member locally`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(mirror = listOf(event("e")))
        repository.details["e"] = EventDetail(
            event("e").copy(registeredCount = 40),
            emptyList(),
        )
        repository.options += MemberOption("m9", "TV-009", "Petra Meyer")
        val viewModel = viewModel(repository)
        viewModel.load("e")
        advanceUntilIdle()

        repository.detailFailure = ApiError.Network(IOException("gone"))
        viewModel.pickMember(repository.options.single())
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventDetailUiState.Content
        assertTrue(state.registrations.single().isWaitlisted)
        assertEquals(40, state.event.registeredCount)
    }

    @Test
    fun `a failed board registration flags the failure and adds nothing`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(mirror = listOf(event("e")))
        repository.details["e"] = EventDetail(event("e"), emptyList())
        val viewModel = viewModel(repository)
        viewModel.load("e")
        advanceUntilIdle()

        repository.actionFailure = ApiError.Forbidden
        viewModel.pickMember(MemberOption("m9", "TV-009", "Petra Meyer"))
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventDetailUiState.Content
        assertTrue(state.registrations.isEmpty())
        assertTrue(state.actionFailed)
        assertEquals(null, viewModel.picker.value.pendingMemberId)

        viewModel.onActionFailedShown()
        advanceUntilIdle()
        assertFalse((viewModel.uiState.value as EventDetailUiState.Content).actionFailed)
    }

    @Test
    fun `removing a registration drops the row and frees the spot`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(mirror = listOf(event("e")))
        repository.details["e"] = EventDetail(
            event("e").copy(registeredCount = 2),
            listOf(
                registration("r1", "Susanne Bauer"),
                registration("r2", "Stefan Weber"),
            ),
        )
        val viewModel = viewModel(repository)
        viewModel.load("e")
        advanceUntilIdle()

        repository.detailFailure = ApiError.Network(IOException("gone"))
        viewModel.removeRegistration("r1")
        advanceUntilIdle()

        assertTrue("r1" in repository.boardRemoved)
        val state = viewModel.uiState.value as EventDetailUiState.Content
        assertEquals(listOf("Stefan Weber"), state.registrations.map { it.memberName })
        assertEquals(1, state.event.registeredCount)
        assertTrue(state.removing.isEmpty())
    }

    /** Removing a waitlisted name must not shrink the registered count. */
    @Test
    fun `removing a waitlisted registration keeps the count`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(mirror = listOf(event("e")))
        repository.details["e"] = EventDetail(
            event("e").copy(registeredCount = 40),
            listOf(
                EventRegistration("r1", "m1", "Petra Meyer", "waitlist", null),
            ),
        )
        val viewModel = viewModel(repository)
        viewModel.load("e")
        advanceUntilIdle()

        repository.detailFailure = ApiError.Network(IOException("gone"))
        viewModel.removeRegistration("r1")
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventDetailUiState.Content
        assertTrue(state.registrations.isEmpty())
        assertEquals(40, state.event.registeredCount)
    }

    @Test
    fun `a failed removal flags the failure and keeps the row`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(mirror = listOf(event("e")))
        repository.details["e"] = EventDetail(
            event("e").copy(registeredCount = 1),
            listOf(registration("r1", "Susanne Bauer")),
        )
        val viewModel = viewModel(repository)
        viewModel.load("e")
        advanceUntilIdle()

        repository.actionFailure = ApiError.Forbidden
        viewModel.removeRegistration("r1")
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventDetailUiState.Content
        assertEquals(listOf("Susanne Bauer"), state.registrations.map { it.memberName })
        assertTrue(state.actionFailed)
        assertTrue(state.removing.isEmpty())
    }

    /** An answer for an outdated query must not overwrite the newer list. */
    @Test
    fun `the picker filters by the query`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(mirror = listOf(event("e")))
        repository.details["e"] = EventDetail(event("e"), emptyList())
        repository.options += MemberOption("m1", "TV-001", "Susanne Bauer")
        repository.options += MemberOption("m2", "TV-002", "Stefan Weber")
        val viewModel = viewModel(repository)
        viewModel.load("e")
        advanceUntilIdle()

        viewModel.openPicker()
        advanceUntilIdle()
        assertEquals(2, viewModel.picker.value.options.size)

        viewModel.setPickerQuery("Weber")
        advanceUntilIdle()
        assertEquals(listOf("Stefan Weber"), viewModel.picker.value.options.map { it.name })
    }

    /** Subscribes on [TestScope.backgroundScope] — `WhileSubscribed` needs a collector. */
    private fun TestScope.viewModel(
        repository: EventsRepository,
        online: MutableStateFlow<Boolean> = MutableStateFlow(true),
    ) = EventDetailViewModel(
        repository,
        EventsClock { "2026-06-01T12:00:00Z" },
        ConnectivityMonitor { online },
    ).also { vm ->
        backgroundScope.launch { vm.uiState.collect {} }
    }

    private fun event(id: String) = Event(
        id = id,
        title = "Termin $id",
        description = null,
        type = null,
        location = null,
        startsAt = "2026-09-10T19:00:00Z",
        endsAt = null,
        allDay = false,
        registrationRequired = true,
        registrationDeadline = null,
        registeredCount = 0,
        maxParticipants = 40,
        status = null,
        isRegistered = false,
    )

    private fun registration(id: String, name: String) =
        EventRegistration(id = id, memberId = "m-$id", memberName = name, status = "registered", note = null)
}

/** Stands in for Room plus the single-event endpoint. */
private class FakeDetailRepository(
    mirror: List<Event>,
) : EventsRepository {

    val mirror = MutableStateFlow(mirror)
    val details = mutableMapOf<String, EventDetail>()
    val registered = mutableSetOf<String>()
    val options = mutableListOf<MemberOption>()
    val boardRegistered = mutableSetOf<String>()
    val boardRemoved = mutableSetOf<String>()
    var detailFailure: ApiError? = null
    var actionFailure: ApiError? = null
    var optionsFailure: ApiError? = null

    override fun stream(): Flow<List<Event>> = mirror

    override fun hasSynced(): Flow<Boolean> = MutableStateFlow(true)

    override fun byIdStream(id: String): Flow<Event?> =
        mirror.map { list -> list.find { it.id == id } }

    override suspend fun detail(id: String): ApiResult<EventDetail> {
        detailFailure?.let { return ApiResult.Failure(it) }
        return details[id]?.let { ApiResult.Success(it) }
            ?: ApiResult.Failure(ApiError.NotFound(null))
    }

    override suspend fun overlay(): ApiResult<Map<String, EventOverlay>> =
        ApiResult.Success(emptyMap())

    override suspend fun register(eventId: String): ApiResult<Unit> {
        actionFailure?.let { return ApiResult.Failure(it) }
        registered += eventId
        return ApiResult.Success(Unit)
    }

    override suspend fun unregister(eventId: String): ApiResult<Unit> {
        actionFailure?.let { return ApiResult.Failure(it) }
        registered -= eventId
        return ApiResult.Success(Unit)
    }

    override suspend fun registerMember(eventId: String, memberId: String): ApiResult<String> {
        actionFailure?.let { return ApiResult.Failure(it) }
        boardRegistered += memberId
        return ApiResult.Success("r-$memberId")
    }

    override suspend fun removeRegistration(
        eventId: String,
        registrationId: String,
    ): ApiResult<Unit> {
        actionFailure?.let { return ApiResult.Failure(it) }
        boardRemoved += registrationId
        return ApiResult.Success(Unit)
    }

    override suspend fun memberOptions(search: String?): ApiResult<List<MemberOption>> {
        optionsFailure?.let { return ApiResult.Failure(it) }
        return ApiResult.Success(
            options.filter { search.isNullOrBlank() || it.name.contains(search, true) },
        )
    }
}
