package com.unefy.feature.events

import com.unefy.core.model.Event
import com.unefy.core.model.EventDetail
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import com.unefy.core.sync.ConnectivityMonitor
import com.unefy.core.sync.SyncStatus
import com.unefy.core.testing.FakeCoordinator
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
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * The event list reads the local mirror; what only the server knows — who is
 * registered, how many are — is an overlay fetched online. These tests pin the
 * merge, the local upcoming/past split, and the write path that must not revert
 * while the safety lag keeps the mirror behind.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class EventsViewModelTest {

    private val dispatcher = StandardTestDispatcher()
    private val now = "2026-06-01T12:00:00Z"

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `an unsynced mirror is Loading, not empty`() = runTest(dispatcher) {
        val viewModel = viewModel(FakeEventsRepository(hasSynced = false))
        advanceUntilIdle()

        assertEquals(EventsUiState.Loading, viewModel.uiState.value)
    }

    @Test
    fun `events are split into upcoming and past around now`() = runTest(dispatcher) {
        val viewModel = viewModel(
            repository(event("past", "2026-01-10T19:00:00Z"), event("future", "2026-09-10T19:00:00Z")),
        )
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventsUiState.Content
        assertEquals(listOf("future"), state.upcoming.map { it.id })
        assertEquals(listOf("past"), state.past.map { it.id })
    }

    @Test
    fun `upcoming runs soonest first, past runs most recent first`() = runTest(dispatcher) {
        val viewModel = viewModel(
            repository(
                event("sooner", "2026-07-01T19:00:00Z"),
                event("later", "2026-12-01T19:00:00Z"),
                event("old", "2025-01-01T19:00:00Z"),
                event("recent", "2026-05-01T19:00:00Z"),
            ),
        )
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventsUiState.Content
        assertEquals(listOf("sooner", "later"), state.upcoming.map { it.id })
        assertEquals(listOf("recent", "old"), state.past.map { it.id })
    }

    /** The mirror knows the rows; the overlay knows what only the server can. */
    @Test
    fun `the overlay fills registration state, count and competition name`() = runTest(dispatcher) {
        val repository = repository(event("e", "2026-09-10T19:00:00Z"))
        repository.overlays["e"] = EventOverlay(
            isRegistered = true,
            registeredCount = 12,
            competitionName = "Königsschießen",
        )
        val viewModel = viewModel(repository)
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventsUiState.Content
        val row = state.upcoming.single()
        assertTrue(row.isRegistered)
        assertEquals(12, row.registeredCount)
        assertEquals("Königsschießen", row.competitionName)
        assertEquals(setOf("e"), state.overlaid)
    }

    /** Without an overlay answer the row stays bare, and the screen knows it. */
    @Test
    fun `an event outside the overlay window is not claimed unregistered`() = runTest(dispatcher) {
        val repository = repository(event("e", "2026-09-10T19:00:00Z"))
        repository.overlayFailure = ApiError.Network(IOException("offline"))
        val viewModel = viewModel(repository)
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventsUiState.Content
        assertEquals(emptySet<String>(), state.overlaid)
        assertEquals(0, state.upcoming.single().registeredCount)
    }

    /**
     * The regression test for the write path. The mirror lags the server by the
     * safety window, so a reload after registering would show the *old* state
     * and flip the button back for six seconds. The confirmed result must land
     * in the overlay and stay there — no reload, no revert.
     */
    @Test
    fun `a successful registration holds without a reload`() = runTest(dispatcher) {
        val repository = repository(event("e", "2026-09-10T19:00:00Z"))
        repository.overlays["e"] = EventOverlay(false, 5, null)
        val viewModel = viewModel(repository)
        advanceUntilIdle()
        val overlayFetches = repository.overlayCalls

        val target = (viewModel.uiState.value as EventsUiState.Content).upcoming.single()
        viewModel.toggleRegistration(target)
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventsUiState.Content
        val row = state.upcoming.single()
        assertTrue(repository.registered.contains("e"))
        assertTrue(row.isRegistered)
        assertEquals(6, row.registeredCount)
        assertTrue(state.pending.isEmpty())
        assertEquals(overlayFetches, repository.overlayCalls)
    }

    @Test
    fun `unregistering decrements the count and clears the flag`() = runTest(dispatcher) {
        val repository = repository(event("e", "2026-09-10T19:00:00Z"))
        repository.overlays["e"] = EventOverlay(true, 5, null)
        val viewModel = viewModel(repository)
        advanceUntilIdle()

        val target = (viewModel.uiState.value as EventsUiState.Content).upcoming.single()
        viewModel.toggleRegistration(target)
        advanceUntilIdle()

        val row = (viewModel.uiState.value as EventsUiState.Content).upcoming.single()
        assertTrue(!row.isRegistered)
        assertEquals(4, row.registeredCount)
    }

    /** A full event answers with an error; the row must go back, not lie. */
    @Test
    fun `a failed registration releases the row and changes nothing`() = runTest(dispatcher) {
        val repository = repository(event("e", "2026-09-10T19:00:00Z"))
        repository.overlays["e"] = EventOverlay(false, 5, null)
        repository.actionFailure = ApiError.Forbidden
        val viewModel = viewModel(repository)
        advanceUntilIdle()

        val target = (viewModel.uiState.value as EventsUiState.Content).upcoming.single()
        viewModel.toggleRegistration(target)
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventsUiState.Content
        assertTrue(state.pending.isEmpty())
        assertTrue(!state.upcoming.single().isRegistered)
        assertEquals(5, state.upcoming.single().registeredCount)
    }

    /** Toggling a row the overlay never answered for would be a blind write. */
    @Test
    fun `a row without overlay data cannot be toggled`() = runTest(dispatcher) {
        val repository = repository(event("e", "2026-09-10T19:00:00Z"))
        repository.overlayFailure = ApiError.Network(IOException("offline"))
        val viewModel = viewModel(repository)
        advanceUntilIdle()

        val target = (viewModel.uiState.value as EventsUiState.Content).upcoming.single()
        viewModel.toggleRegistration(target)
        advanceUntilIdle()

        assertTrue(repository.registered.isEmpty())
    }

    /** Registrations made while the device could not hear must surface. */
    @Test
    fun `coming back online refetches the overlay`() = runTest(dispatcher) {
        val repository = repository(event("e", "2026-09-10T19:00:00Z"))
        val online = MutableStateFlow(true)
        val viewModel = viewModel(repository, online = online)
        advanceUntilIdle()
        val afterStart = repository.overlayCalls

        online.value = false
        advanceUntilIdle()
        online.value = true
        advanceUntilIdle()

        assertEquals(afterStart + 1, repository.overlayCalls)
    }

    @Test
    fun `a sync failure keeps the list and reports why it is stale`() = runTest(dispatcher) {
        val repository = repository(event("e", "2026-09-10T19:00:00Z"))
        val coordinator = FakeCoordinator()
        val viewModel = viewModel(repository, coordinator)
        advanceUntilIdle()

        coordinator.status.value = SyncStatus.Failed(ApiError.Network(IOException("no signal")))
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventsUiState.Content
        assertEquals(listOf("e"), state.upcoming.map { it.id })
        assertTrue(state.staleBecause is ApiError.Network)

        coordinator.status.value = SyncStatus.Idle
        advanceUntilIdle()
        assertNull((viewModel.uiState.value as EventsUiState.Content).staleBecause)
    }

    @Test
    fun `a sync failure with an empty mirror is a Failure`() = runTest(dispatcher) {
        val coordinator = FakeCoordinator(SyncStatus.Failed(ApiError.Network(IOException())))
        val viewModel = viewModel(FakeEventsRepository(hasSynced = false), coordinator)
        advanceUntilIdle()

        assertTrue(viewModel.uiState.value is EventsUiState.Failure)
    }

    @Test
    fun `a second refresh while one is running is ignored`() = runTest(dispatcher) {
        val coordinator = FakeCoordinator(blockSync = true)
        val viewModel = viewModel(repository(), coordinator)
        advanceUntilIdle()

        viewModel.refresh()
        viewModel.refresh()
        viewModel.refresh()
        advanceUntilIdle()

        assertEquals(1, coordinator.syncedNow.size)
    }

    /** A cap of zero must not divide by zero — capacityRatio is null instead. */
    @Test
    fun `capacity ratio is null without a usable cap`() {
        assertEquals(null, event("a", now, max = null).capacityRatio)
        assertEquals(null, event("b", now, max = 0).capacityRatio)
        assertEquals(
            0.5f,
            event("c", now, max = 10).copy(registeredCount = 5).capacityRatio,
        )
    }

    @Test
    fun `registration closes at the deadline, when full, and once started`() {
        val open = event("a", "2026-09-10T19:00:00Z", max = 10)
        assertTrue(open.registrationOpen(now))

        val expired = event("b", "2026-09-10T19:00:00Z", max = 10, deadline = "2026-05-01T00:00:00Z")
        assertTrue(!expired.registrationOpen(now))

        val full = event("c", "2026-09-10T19:00:00Z", max = 2).copy(registeredCount = 2)
        assertTrue(!full.registrationOpen(now))

        val started = event("d", "2026-01-10T19:00:00Z", max = 10)
        assertTrue(!started.registrationOpen(now))
    }

    private fun repository(vararg events: Event) = FakeEventsRepository(events.toList())

    /** Subscribes on [TestScope.backgroundScope] — `WhileSubscribed` needs a collector. */
    private fun TestScope.viewModel(
        repository: EventsRepository,
        coordinator: FakeCoordinator = FakeCoordinator(),
        online: MutableStateFlow<Boolean> = MutableStateFlow(true),
    ) = EventsViewModel(
        repository,
        coordinator,
        EventsClock { now },
        ConnectivityMonitor { online },
    ).also { vm ->
        backgroundScope.launch { vm.uiState.collect {} }
    }

    private fun event(
        id: String,
        startsAt: String,
        max: Int? = null,
        deadline: String? = null,
    ) = Event(
        id = id,
        title = "Termin $id",
        description = null,
        type = null,
        location = null,
        startsAt = startsAt,
        endsAt = null,
        allDay = false,
        registrationRequired = true,
        registrationDeadline = deadline,
        registeredCount = 0,
        maxParticipants = max,
        status = null,
        isRegistered = false,
    )
}

/** Stands in for Room plus the list endpoint. [rows] is the mirror, [overlays] the server. */
private class FakeEventsRepository(
    events: List<Event> = emptyList(),
    private val hasSynced: Boolean = true,
) : EventsRepository {

    val rows = MutableStateFlow(events)
    val overlays = mutableMapOf<String, EventOverlay>()
    val registered = mutableSetOf<String>()
    var overlayFailure: ApiError? = null
    var actionFailure: ApiError? = null
    var overlayCalls = 0
        private set

    override fun stream(): Flow<List<Event>> = rows

    override fun hasSynced(): Flow<Boolean> = MutableStateFlow(hasSynced)

    override fun byIdStream(id: String): Flow<Event?> =
        rows.map { list -> list.find { it.id == id } }

    override suspend fun detail(id: String): ApiResult<EventDetail> =
        ApiResult.Failure(ApiError.NotFound(null))

    override suspend fun overlay(): ApiResult<Map<String, EventOverlay>> {
        overlayCalls++
        overlayFailure?.let { return ApiResult.Failure(it) }
        return ApiResult.Success(overlays.toMap())
    }

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

    override suspend fun registerMember(eventId: String, memberId: String): ApiResult<String> =
        ApiResult.Success("r-$memberId")

    override suspend fun removeRegistration(
        eventId: String,
        registrationId: String,
    ): ApiResult<Unit> = ApiResult.Success(Unit)

    override suspend fun memberOptions(search: String?): ApiResult<List<MemberOption>> =
        ApiResult.Success(emptyList())
}
