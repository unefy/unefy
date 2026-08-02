package com.unefy.feature.events

import com.unefy.core.model.Event
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiMeta
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

    /**
     * The regression this whole change exists for. The backend pages ascending
     * from the oldest event, so with one unfiltered stream a club with more past
     * events than fit on a page had an empty "Kommend" section — the answer to
     * the only question most members open this screen with.
     */
    @Test
    fun `upcoming events survive a club with more history than one page`() = runTest(dispatcher) {
        val history = (1..60).map { event("past-$it", "2020-01-01T19:00:00Z".withDay(it)) }
        val repository = FakeEventsRepository(history + event("soon", "2026-09-10T19:00:00Z"))
        val viewModel = EventsViewModel(repository, EventsClock { now })
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventsUiState.Content
        assertEquals(listOf("soon"), state.upcoming.map { it.id })
        // Most recent first, and only the first page of them.
        assertEquals("past-60", state.past.first().id)
        assertEquals(50, state.past.size)
    }

    @Test
    fun `load more walks past events back through the pages`() = runTest(dispatcher) {
        val history = (1..60).map { event("past-$it", "2020-01-01T19:00:00Z".withDay(it)) }
        val viewModel = EventsViewModel(FakeEventsRepository(history), EventsClock { now })
        advanceUntilIdle()
        assertEquals(50, (viewModel.uiState.value as EventsUiState.Content).past.size)

        viewModel.loadMore()
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventsUiState.Content
        assertEquals(60, state.past.size)
        assertEquals(60, state.past.distinctBy { it.id }.size)
        assertTrue(!state.isLoadingMore)
    }

    /** The scroll listener fires on position and knows nothing about pages. */
    @Test
    fun `load more past the last page asks for nothing`() = runTest(dispatcher) {
        val repository = FakeEventsRepository(listOf(event("only", "2026-09-10T19:00:00Z")))
        val viewModel = EventsViewModel(repository, EventsClock { now })
        advanceUntilIdle()
        val afterLoad = repository.requests.size

        repeat(5) { viewModel.loadMore() }
        advanceUntilIdle()

        assertEquals(afterLoad, repository.requests.size)
    }

    @Test
    fun `a refresh picks up what was added elsewhere`() = runTest(dispatcher) {
        val repository = FakeEventsRepository(listOf(event("known", "2026-09-10T19:00:00Z")))
        val viewModel = EventsViewModel(repository, EventsClock { now })
        advanceUntilIdle()

        repository.events = repository.events + event("added", "2026-10-10T19:00:00Z")
        viewModel.refresh()
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventsUiState.Content
        assertEquals(listOf("known", "added"), state.upcoming.map { it.id })
        assertTrue(!state.isRefreshing)
    }

    @Test
    fun `a failing refresh keeps the list and reports the failure`() = runTest(dispatcher) {
        val repository = FakeEventsRepository(listOf(event("e", "2026-09-10T19:00:00Z")))
        val viewModel = EventsViewModel(repository, EventsClock { now })
        advanceUntilIdle()

        repository.failure = ApiError.Network(java.io.IOException("offline"))
        viewModel.refresh()
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventsUiState.Content
        assertEquals(listOf("e"), state.upcoming.map { it.id })
        assertTrue(state.refreshFailed)
        assertTrue(!state.isRefreshing)

        viewModel.onMessageShown()
        assertTrue(!(viewModel.uiState.value as EventsUiState.Content).refreshFailed)
    }

    /**
     * The reload after a registration goes through the same failure path. If it
     * left `pending` set, that row would stay locked with no way back.
     */
    @Test
    fun `a reload that fails after registering still releases the row`() = runTest(dispatcher) {
        val repository = FakeEventsRepository(listOf(event("e", "2026-09-10T19:00:00Z")))
        val viewModel = EventsViewModel(repository, EventsClock { now })
        advanceUntilIdle()

        val target = (viewModel.uiState.value as EventsUiState.Content).upcoming.single()
        repository.failOnNextList = ApiError.Network(java.io.IOException("offline"))
        viewModel.toggleRegistration(target)
        advanceUntilIdle()

        val state = viewModel.uiState.value as EventsUiState.Content
        assertTrue(state.pending.isEmpty())
        assertTrue(state.refreshFailed)
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

    /**
     * Distinct, ordered timestamps for bulk fixtures. Not all of them are real
     * calendar dates — day 60 is not — and none of them need to be: everything
     * under test compares these as strings, exactly as the ViewModel does.
     */
    private fun String.withDay(day: Int) = replaceRange(8, 10, "%02d".format(day))

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
    var failure: ApiError? = null,
    private val actionFailure: ApiError? = null,
) : EventsRepository {
    val registered = mutableSetOf<String>()

    /** Fails one list call and then clears itself — for the reload after a write. */
    var failOnNextList: ApiError? = null

    /** Every (page, per_page) the ViewModel asked for, in order. */
    val requests = mutableListOf<Triple<Int, String?, String?>>()

    /**
     * Filters, orders and pages the way the backend does. A fake that ignored
     * the window would let a ViewModel that never sends one pass.
     */
    override suspend fun list(
        page: Int,
        perPage: Int,
        startsAfter: String?,
        startsBefore: String?,
        newestFirst: Boolean,
    ): ApiResult<List<Event>> {
        requests += Triple(page, startsAfter, startsBefore)
        failOnNextList?.let {
            failOnNextList = null
            return ApiResult.Failure(it)
        }
        failure?.let { return ApiResult.Failure(it) }

        val window = events
            .filter { startsAfter == null || it.startsAt >= startsAfter }
            .filter { startsBefore == null || it.startsAt < startsBefore }
            .let { if (newestFirst) it.sortedByDescending { e -> e.startsAt } else it.sortedBy { e -> e.startsAt } }

        val from = (page - 1) * perPage
        val slice = window.drop(from).take(perPage)
        val totalPages = if (window.isEmpty()) 1 else (window.size + perPage - 1) / perPage
        return ApiResult.Success(
            slice,
            ApiMeta(total = window.size, page = page, perPage = perPage, totalPages = totalPages),
        )
    }

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
