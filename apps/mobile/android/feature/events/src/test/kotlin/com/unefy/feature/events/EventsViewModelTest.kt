package com.unefy.feature.events

import com.unefy.core.model.Event
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class EventsViewModelTest {

    private val dispatcher = StandardTestDispatcher()
    private val now = "2026-06-01T12:00:00Z"

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `events are split into upcoming and past around now`() = runTest(dispatcher) {
        val viewModel = viewModel(
            event("past", "2026-01-10T19:00:00Z"),
            event("future", "2026-09-10T19:00:00Z"),
        )
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventsUiState.Content
        assertEquals(listOf("future"), state.upcoming.map { it.id })
        assertEquals(listOf("past"), state.past.map { it.id })
    }

    @Test
    fun `upcoming runs soonest first, past runs most recent first`() = runTest(dispatcher) {
        val viewModel = viewModel(
            event("later", "2026-12-01T19:00:00Z"),
            event("sooner", "2026-07-01T19:00:00Z"),
            event("old", "2025-01-01T19:00:00Z"),
            event("recent", "2026-05-01T19:00:00Z"),
        )
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventsUiState.Content
        assertEquals(listOf("sooner", "later"), state.upcoming.map { it.id })
        assertEquals(listOf("recent", "old"), state.past.map { it.id })
    }

    @Test
    fun `a failing load surfaces the typed error`() = runTest(dispatcher) {
        val viewModel = EventsViewModel(
            FakeEventsRepository(failure = ApiError.Forbidden),
            EventsClock { now },
        )
        advanceUntilIdle()

        assertTrue(viewModel.uiState.value is EventsUiState.Failure)
    }

    /** A cap of zero must not divide by zero — capacityRatio is null instead. */
    @Test
    fun `capacity ratio is null without a usable cap`() {
        assertEquals(null, event("a", now, max = null).capacityRatio)
        assertEquals(null, event("b", now, max = 0).capacityRatio)
        assertEquals(0.5f, event("c", now, max = 10, registered = 5).capacityRatio)
    }

    @Test
    fun `registering reloads so the row reflects the server, not a guess`() = runTest(dispatcher) {
        val repository = FakeEventsRepository(listOf(event("e", "2026-09-10T19:00:00Z")))
        val viewModel = EventsViewModel(repository, EventsClock { now })
        advanceUntilIdle()

        val target = (viewModel.uiState.value as EventsUiState.Content).upcoming.single()
        viewModel.toggleRegistration(target)
        advanceUntilIdle()

        assertTrue(repository.registered.contains("e"))
        val state = viewModel.uiState.value as EventsUiState.Content
        assertTrue(state.upcoming.single().isRegistered)
        assertTrue(state.pending.isEmpty())
    }

    /** A full event answers with an error; the row must go back, not lie. */
    @Test
    fun `a failed registration releases the row and changes nothing`() = runTest(dispatcher) {
        val repository = FakeEventsRepository(
            events = listOf(event("e", "2026-09-10T19:00:00Z")),
            actionFailure = ApiError.Forbidden,
        )
        val viewModel = EventsViewModel(repository, EventsClock { now })
        advanceUntilIdle()

        val target = (viewModel.uiState.value as EventsUiState.Content).upcoming.single()
        viewModel.toggleRegistration(target)
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventsUiState.Content
        assertTrue(state.pending.isEmpty())
        assertTrue(!state.upcoming.single().isRegistered)
    }

    @Test
    fun `registration closes at the deadline, when full, and once started`() {
        val open = event("a", "2026-09-10T19:00:00Z", max = 10, registered = 1)
        assertTrue(open.registrationOpen(now))

        val expired = event("b", "2026-09-10T19:00:00Z", max = 10, deadline = "2026-05-01T00:00:00Z")
        assertTrue(!expired.registrationOpen(now))

        val full = event("c", "2026-09-10T19:00:00Z", max = 2, registered = 2)
        assertTrue(!full.registrationOpen(now))

        val started = event("d", "2026-01-10T19:00:00Z", max = 10)
        assertTrue(!started.registrationOpen(now))
    }

    private fun viewModel(vararg events: Event) =
        EventsViewModel(FakeEventsRepository(events.toList()), EventsClock { now })

    private fun event(
        id: String,
        startsAt: String,
        max: Int? = null,
        registered: Int = 0,
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
        registeredCount = registered,
        maxParticipants = max,
        status = null,
        isRegistered = registered > 0 && max == null,
    )
}

private class FakeEventsRepository(
    var events: List<Event> = emptyList(),
    private val failure: ApiError? = null,
    private val actionFailure: ApiError? = null,
) : EventsRepository {
    val registered = mutableSetOf<String>()

    override suspend fun list(page: Int, perPage: Int): ApiResult<List<Event>> =
        failure?.let { ApiResult.Failure(it) } ?: ApiResult.Success(events)

    override suspend fun register(eventId: String): ApiResult<Unit> {
        actionFailure?.let { return ApiResult.Failure(it) }
        registered += eventId
        events = events.map { if (it.id == eventId) it.copy(isRegistered = true) else it }
        return ApiResult.Success(Unit)
    }

    override suspend fun unregister(eventId: String): ApiResult<Unit> {
        actionFailure?.let { return ApiResult.Failure(it) }
        registered -= eventId
        events = events.map { if (it.id == eventId) it.copy(isRegistered = false) else it }
        return ApiResult.Success(Unit)
    }
}
