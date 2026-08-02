package com.unefy.feature.competitions

import com.unefy.core.model.Competition
import com.unefy.core.model.Scoreboard
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
class CompetitionsViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `the current season comes first`() = runTest(dispatcher) {
        val viewModel = CompetitionsViewModel(
            FakeCompetitionsRepository(
                listOf(competition("old", "2023-03-01"), competition("new", "2026-03-01")),
            ),
        )
        advanceUntilIdle()

        val state = viewModel.uiState.value as CompetitionsUiState.Content
        assertEquals(listOf("new", "old"), state.competitions.map { it.id })
    }

    @Test
    fun `a failing load surfaces the typed error`() = runTest(dispatcher) {
        val viewModel = CompetitionsViewModel(
            FakeCompetitionsRepository(failure = ApiError.Forbidden),
        )
        advanceUntilIdle()

        assertTrue(viewModel.uiState.value is CompetitionsUiState.Failure)
    }

    /** The unit travels with the ranking: "1040" means nothing on its own. */
    @Test
    fun `the scoreboard keeps its scoring unit`() = runTest(dispatcher) {
        val viewModel = ScoreboardViewModel(FakeCompetitionsRepository())
        viewModel.load("1")
        advanceUntilIdle()

        val state = viewModel.uiState.value as ScoreboardUiState.Content
        assertEquals("Ringe", state.scoreboard.unit)
        assertTrue(state.scoreboard.highestWins)
    }

    @Test
    fun `highestWins follows the backend rather than being assumed`() {
        assertTrue(competition("a", "2026-01-01").highestWins)
        assertTrue(!competition("b", "2026-01-01", mode = "lowest_wins").highestWins)
    }

    private fun competition(id: String, start: String, mode: String = "highest_wins") = Competition(
        id = id,
        name = "Wettkampf $id",
        description = null,
        type = "competition",
        startDate = start,
        endDate = null,
        scoringUnit = "Ringe",
        scoringMode = mode,
        disciplines = emptyList(),
    )
}

private class FakeCompetitionsRepository(
    private val competitions: List<Competition> = emptyList(),
    private val failure: ApiError? = null,
) : CompetitionsRepository {
    override suspend fun list(): ApiResult<List<Competition>> =
        failure?.let { ApiResult.Failure(it) } ?: ApiResult.Success(competitions)

    override suspend fun scoreboard(competitionId: String): ApiResult<Scoreboard> =
        failure?.let { ApiResult.Failure(it) }
            ?: ApiResult.Success(Scoreboard(unit = "Ringe", highestWins = true, rows = emptyList()))
}
