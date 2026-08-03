package com.unefy.feature.dues

import com.unefy.core.model.DuesEntry
import com.unefy.core.model.DuesStatus
import com.unefy.core.model.DuesSummary
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiMeta
import com.unefy.core.network.ApiResult
import com.unefy.core.sync.SyncStatus
import com.unefy.core.testing.FakeCoordinator
import java.io.IOException
import kotlinx.coroutines.CompletableDeferred
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
 * The board's ledger reads the local mirror now; the chips are a SQL filter,
 * not a reload. MyDues stays an online screen — a plain member may not sync
 * the dues collection — and keeps its paging tests below.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class DuesViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `an unsynced mirror is Loading, not empty`() = runTest(dispatcher) {
        val viewModel = viewModel(FakeDuesRepository(hasSynced = false))
        advanceUntilIdle()

        assertEquals(DuesUiState.Loading, viewModel.uiState.value)
    }

    /** A plain member may not mirror the ledger — the refusal is the screen. */
    @Test
    fun `a refused collection is a Forbidden failure`() = runTest(dispatcher) {
        val coordinator = FakeCoordinator(SyncStatus.NotPermitted)
        val viewModel = viewModel(FakeDuesRepository(hasSynced = false), coordinator)
        advanceUntilIdle()

        assertEquals(DuesUiState.Failure(ApiError.Forbidden), viewModel.uiState.value)
    }

    /**
     * The chips are a local query over the mirror. The count of network calls
     * is the regression test: the old implementation reloaded per chip, and the
     * race between two in-flight reloads once put open dues under "Bezahlt".
     */
    @Test
    fun `a chip change filters locally and makes no network call`() = runTest(dispatcher) {
        val repository = FakeDuesRepository(
            entries = listOf(entry("1", DuesStatus.PAID), entry("2", DuesStatus.OPEN)),
        )
        val viewModel = viewModel(repository)
        advanceUntilIdle()
        val networkCalls = repository.networkCalls

        viewModel.onFilterChange(DuesFilter.OPEN)
        advanceUntilIdle()

        val state = viewModel.uiState.value as DuesUiState.Content
        assertEquals(DuesFilter.OPEN, state.filter)
        assertEquals(listOf("2"), state.entries.map { it.id })
        assertEquals(networkCalls, repository.networkCalls)
    }

    /** Chip and rows move together — never the new chip over the old rows. */
    @Test
    fun `the filter on screen always matches the rows on screen`() = runTest(dispatcher) {
        val repository = FakeDuesRepository(
            entries = listOf(entry("1", DuesStatus.PAID), entry("2", DuesStatus.OPEN)),
        )
        val viewModel = viewModel(repository)
        advanceUntilIdle()

        viewModel.onFilterChange(DuesFilter.PAID)
        advanceUntilIdle()

        val state = viewModel.uiState.value as DuesUiState.Content
        assertEquals(DuesFilter.PAID, state.filter)
        assertEquals(listOf("1"), state.entries.map { it.id })
    }

    /**
     * The list is what the screen is for. A summary that fails to load costs a
     * header, not the screen — it must not turn into an error state.
     */
    @Test
    fun `a failing summary still renders the list`() = runTest(dispatcher) {
        val viewModel = viewModel(
            FakeDuesRepository(
                entries = listOf(entry("1", DuesStatus.OPEN)),
                summaryFailure = ApiError.Forbidden,
            ),
        )
        advanceUntilIdle()

        val state = viewModel.uiState.value as DuesUiState.Content
        assertNull(state.summary)
        assertEquals(1, state.entries.size)
    }

    @Test
    fun `a sync failure keeps the ledger and reports why it is stale`() = runTest(dispatcher) {
        val coordinator = FakeCoordinator()
        val viewModel = viewModel(
            FakeDuesRepository(entries = listOf(entry("1", DuesStatus.OPEN))),
            coordinator,
        )
        advanceUntilIdle()

        coordinator.status.value = SyncStatus.Failed(ApiError.Network(IOException("no signal")))
        advanceUntilIdle()

        val state = viewModel.uiState.value as DuesUiState.Content
        assertEquals(1, state.entries.size)
        assertTrue(state.staleBecause is ApiError.Network)
    }

    @Test
    fun `a second refresh while one is running is ignored`() = runTest(dispatcher) {
        val coordinator = FakeCoordinator(blockSync = true)
        val viewModel = viewModel(FakeDuesRepository(), coordinator)
        advanceUntilIdle()

        viewModel.refresh()
        viewModel.refresh()
        viewModel.refresh()
        advanceUntilIdle()

        assertEquals(1, coordinator.syncedNow.size)
    }

    // ------------------------------------------------------------------
    // MyDues — online, paged, unchanged by the mirror work.
    // ------------------------------------------------------------------

    /**
     * The own-dues screen must never call the club-wide summary — it is
     * board-only and would answer 403.
     */
    @Test
    fun `my dues load without touching the club-wide summary`() = runTest(dispatcher) {
        val repository = FakeDuesRepository(
            entries = listOf(entry("1", DuesStatus.OPEN)),
            summaryFailure = ApiError.Forbidden,
        )
        val viewModel = MyDuesViewModel(repository)
        advanceUntilIdle()

        val state = viewModel.uiState.value as DuesUiState.Content
        assertNull(state.summary)
        assertEquals(1, state.entries.size)
    }

    @Test
    fun `my dues filter asks the backend`() = runTest(dispatcher) {
        val repository = FakeDuesRepository(
            entries = listOf(entry("1", DuesStatus.PAID), entry("2", DuesStatus.OPEN)),
        )
        val viewModel = MyDuesViewModel(repository)
        advanceUntilIdle()

        viewModel.onFilterChange(DuesFilter.OPEN)
        advanceUntilIdle()

        assertEquals("open", repository.lastStatus)
        assertEquals(
            listOf("2"),
            (viewModel.uiState.value as DuesUiState.Content).entries.map { it.id },
        )
    }

    /**
     * The regression test for the filter race. Two chips tapped in a row are two
     * requests in flight; without cancelling the first, its slow response lands
     * last and puts open dues under the "Bezahlt" chip — persistently, because
     * nothing else reloads.
     */
    @Test
    fun `my dues cannot show a stale filter's rows`() = runTest(dispatcher) {
        val repository = FakeDuesRepository(
            entries = listOf(entry("1", DuesStatus.OPEN), entry("2", DuesStatus.PAID)),
        )
        val viewModel = MyDuesViewModel(repository)
        advanceUntilIdle()

        repository.stallStatus = "open"
        viewModel.onFilterChange(DuesFilter.OPEN)
        advanceUntilIdle()

        viewModel.onFilterChange(DuesFilter.PAID)
        advanceUntilIdle()

        repository.releaseStalled()
        advanceUntilIdle()

        val state = viewModel.uiState.value as DuesUiState.Content
        assertEquals(DuesFilter.PAID, state.filter)
        assertEquals(listOf("2"), state.entries.map { it.id })
    }

    @Test
    fun `a failing my-dues list is an error`() = runTest(dispatcher) {
        val viewModel = MyDuesViewModel(FakeDuesRepository(listFailure = ApiError.Unauthorized))
        advanceUntilIdle()

        assertTrue(viewModel.uiState.value is DuesUiState.Failure)
    }

    /** Subscribes on [TestScope.backgroundScope] — `WhileSubscribed` needs a collector. */
    private fun TestScope.viewModel(
        repository: DuesRepository,
        coordinator: FakeCoordinator = FakeCoordinator(),
    ) = DuesViewModel(repository, coordinator).also { vm ->
        backgroundScope.launch { vm.uiState.collect {} }
    }

    private fun entry(id: String, status: DuesStatus) = DuesEntry(
        id = id,
        memberId = "m$id",
        memberName = "Mitglied $id",
        feeName = "Erwachsene",
        amount = "120.00",
        dueDate = "2025-01-31",
        status = status,
        paidAt = null,
    )
}

/**
 * Stands in for both sources: [rows] plays the Room mirror (stream filters it
 * the way the DAO's SQL does), and `mine` plays the paged backend. The two are
 * deliberately one fake — the tests above assert which of them gets asked.
 */
private class FakeDuesRepository(
    entries: List<DuesEntry> = emptyList(),
    var listFailure: ApiError? = null,
    private val summaryFailure: ApiError? = null,
    private val hasSynced: Boolean = true,
) : DuesRepository {

    val rows = MutableStateFlow(entries)

    /** The status of the most recent network call, or null if none was sent. */
    var lastStatus: String? = null
        private set

    /** Network requests made — a chip change on the mirror must not add any. */
    var networkCalls = 0
        private set

    /** Requests for this status park on a gate until [releaseStalled]. */
    var stallStatus: String? = null
    private val stallGate = CompletableDeferred<Unit>()

    fun releaseStalled() {
        stallGate.complete(Unit)
    }

    override fun stream(status: String?): Flow<List<DuesEntry>> = rows.map { list ->
        list.filter { status == null || it.status.apiValue == status }
    }

    override fun hasSynced(): Flow<Boolean> = MutableStateFlow(hasSynced)

    override suspend fun mine(
        page: Int,
        perPage: Int,
        status: String?,
    ): ApiResult<List<DuesEntry>> {
        networkCalls++
        lastStatus = status
        if (status != null && status == stallStatus) stallGate.await()
        listFailure?.let { return ApiResult.Failure(it) }

        val matching = rows.value.filter { status == null || it.status.apiValue == status }
        val totalPages = if (matching.isEmpty()) 1 else (matching.size + perPage - 1) / perPage
        return ApiResult.Success(
            matching.drop((page - 1) * perPage).take(perPage),
            ApiMeta(total = matching.size, page = page, perPage = perPage, totalPages = totalPages),
        )
    }

    override suspend fun summary(): ApiResult<DuesSummary> {
        networkCalls++
        return summaryFailure?.let { ApiResult.Failure(it) }
            ?: ApiResult.Success(DuesSummary(1, "120.00", 2, "240.00"))
    }
}
