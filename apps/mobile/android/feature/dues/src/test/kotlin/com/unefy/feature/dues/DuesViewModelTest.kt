package com.unefy.feature.dues

import com.unefy.core.model.DuesEntry
import com.unefy.core.model.DuesStatus
import com.unefy.core.model.DuesSummary
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
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class DuesViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    /**
     * The chips are a query, not a list operation. Filtering the loaded pages
     * made "offen" mean "the open ones among the first fifty rows", which for a
     * ledger of any size is a different and much smaller number.
     */
    @Test
    fun `the open filter asks the backend for open dues`() = runTest(dispatcher) {
        val repository = FakeDuesRepository(
            entries = listOf(
                entry("1", DuesStatus.PAID),
                entry("2", DuesStatus.OPEN),
                entry("3", DuesStatus.CANCELLED),
            ),
        )
        val viewModel = DuesViewModel(repository)
        advanceUntilIdle()

        viewModel.onFilterChange(DuesFilter.OPEN)
        advanceUntilIdle()

        assertEquals("open", repository.lastStatus)
        assertEquals(listOf("2"), (viewModel.uiState.value as DuesUiState.Content).entries.map { it.id })
    }

    @Test
    fun `the paid filter asks the backend for paid dues`() = runTest(dispatcher) {
        val repository = FakeDuesRepository(
            entries = listOf(entry("1", DuesStatus.PAID), entry("2", DuesStatus.OPEN)),
        )
        val viewModel = DuesViewModel(repository)
        advanceUntilIdle()

        viewModel.onFilterChange(DuesFilter.PAID)
        advanceUntilIdle()

        assertEquals("paid", repository.lastStatus)
        assertEquals(listOf("1"), (viewModel.uiState.value as DuesUiState.Content).entries.map { it.id })
    }

    /** All means all — no status parameter at all, not one that says "any". */
    @Test
    fun `the all filter sends no status`() = runTest(dispatcher) {
        val repository = FakeDuesRepository(entries = listOf(entry("1", DuesStatus.OPEN)))
        val viewModel = DuesViewModel(repository)
        advanceUntilIdle()

        viewModel.onFilterChange(DuesFilter.PAID)
        advanceUntilIdle()
        viewModel.onFilterChange(DuesFilter.ALL)
        advanceUntilIdle()

        assertNull(repository.lastStatus)
    }

    /** Pages have to carry the filter, or page two would ignore the chip. */
    @Test
    fun `paging stays inside the active filter`() = runTest(dispatcher) {
        val repository = FakeDuesRepository(entries = (1..70).map { entry("$it", DuesStatus.OPEN) })
        val viewModel = DuesViewModel(repository)
        advanceUntilIdle()

        viewModel.onFilterChange(DuesFilter.OPEN)
        advanceUntilIdle()
        viewModel.loadMore()
        advanceUntilIdle()

        assertEquals("open", repository.lastStatus)
        assertEquals(70, (viewModel.uiState.value as DuesUiState.Content).entries.size)
    }

    /**
     * Rows from the old filter under a chip that says "offen" would be a lie, so
     * a filter change that fails shows the error rather than keeping them.
     */
    @Test
    fun `a filter change that fails shows the error`() = runTest(dispatcher) {
        val repository = FakeDuesRepository(entries = listOf(entry("1", DuesStatus.PAID)))
        val viewModel = DuesViewModel(repository)
        advanceUntilIdle()

        repository.listFailure = ApiError.Forbidden
        viewModel.onFilterChange(DuesFilter.OPEN)
        advanceUntilIdle()

        assertTrue(viewModel.uiState.value is DuesUiState.Failure)
    }

    /**
     * The list is what the screen is for. A summary that fails to load costs a
     * header, not the screen — it must not turn into an error state.
     */
    @Test
    fun `a failing summary still renders the list`() = runTest(dispatcher) {
        val viewModel = DuesViewModel(
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
    fun `a failing list is an error even when the summary succeeds`() = runTest(dispatcher) {
        val viewModel = DuesViewModel(FakeDuesRepository(listFailure = ApiError.Unauthorized))
        advanceUntilIdle()

        assertTrue(viewModel.uiState.value is DuesUiState.Failure)
    }

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

private class FakeDuesRepository(
    private val entries: List<DuesEntry> = emptyList(),
    var listFailure: ApiError? = null,
    private val summaryFailure: ApiError? = null,
) : DuesRepository {

    /** The status of the most recent call, or null if none was sent. */
    var lastStatus: String? = null
        private set

    /** Filters and pages the way the backend does, status parameter included. */
    private fun pageOf(page: Int, perPage: Int, status: String?): ApiResult<List<DuesEntry>> {
        lastStatus = status
        listFailure?.let { return ApiResult.Failure(it) }

        val matching = entries.filter { status == null || it.status.apiValue == status }
        val totalPages = if (matching.isEmpty()) 1 else (matching.size + perPage - 1) / perPage
        return ApiResult.Success(
            matching.drop((page - 1) * perPage).take(perPage),
            ApiMeta(total = matching.size, page = page, perPage = perPage, totalPages = totalPages),
        )
    }

    override suspend fun list(page: Int, perPage: Int, status: String?) = pageOf(page, perPage, status)

    override suspend fun mine(page: Int, perPage: Int, status: String?) = pageOf(page, perPage, status)

    override suspend fun summary(): ApiResult<DuesSummary> =
        summaryFailure?.let { ApiResult.Failure(it) }
            ?: ApiResult.Success(DuesSummary(1, "120.00", 2, "240.00"))
}
