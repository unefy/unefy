package com.unefy.feature.dues

import com.unefy.core.model.DuesEntry
import com.unefy.core.model.DuesStatus
import com.unefy.core.model.DuesSummary
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

    @Test
    fun `the open filter keeps everything that is not paid`() = runTest(dispatcher) {
        val viewModel = DuesViewModel(
            FakeDuesRepository(
                entries = listOf(
                    entry("1", DuesStatus.PAID),
                    entry("2", DuesStatus.OPEN),
                    entry("3", DuesStatus.OVERDUE),
                ),
            ),
        )
        advanceUntilIdle()

        viewModel.onFilterChange(DuesFilter.OPEN)
        val state = viewModel.uiState.value as DuesUiState.Content
        assertEquals(listOf("2", "3"), state.visible.map { it.id })
    }

    @Test
    fun `the paid filter keeps only paid items`() = runTest(dispatcher) {
        val viewModel = DuesViewModel(
            FakeDuesRepository(entries = listOf(entry("1", DuesStatus.PAID), entry("2", DuesStatus.OPEN))),
        )
        advanceUntilIdle()

        viewModel.onFilterChange(DuesFilter.PAID)
        assertEquals(listOf("1"), (viewModel.uiState.value as DuesUiState.Content).visible.map { it.id })
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
    private val listFailure: ApiError? = null,
    private val summaryFailure: ApiError? = null,
) : DuesRepository {
    override suspend fun list(page: Int, perPage: Int): ApiResult<List<DuesEntry>> =
        listFailure?.let { ApiResult.Failure(it) } ?: ApiResult.Success(entries)

    override suspend fun mine(page: Int, perPage: Int): ApiResult<List<DuesEntry>> =
        listFailure?.let { ApiResult.Failure(it) } ?: ApiResult.Success(entries)

    override suspend fun summary(): ApiResult<DuesSummary> =
        summaryFailure?.let { ApiResult.Failure(it) }
            ?: ApiResult.Success(DuesSummary(1, "120.00", 2, "240.00"))
}
