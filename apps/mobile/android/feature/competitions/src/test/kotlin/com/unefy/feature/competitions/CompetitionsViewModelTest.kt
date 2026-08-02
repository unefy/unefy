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

    /**
     * The whole point of the gesture: the list on screen is a snapshot, and a
     * refresh has to replace it with what the backend has now.
     */
    @Test
    fun `a refresh picks up what was added elsewhere`() = runTest(dispatcher) {
        val repository = FakeCompetitionsRepository(listOf(competition("old", "2023-03-01")))
        val viewModel = CompetitionsViewModel(repository)
        advanceUntilIdle()

        repository.competitions = listOf(
            competition("old", "2023-03-01"),
            competition("fresh", "2026-03-01"),
        )
        viewModel.refresh()
        advanceUntilIdle()

        val state = viewModel.uiState.value as CompetitionsUiState.Content
        assertEquals(listOf("fresh", "old"), state.competitions.map { it.id })
        assertTrue(!state.isRefreshing)
    }

    /**
     * A dropped connection must not cost the user the list they already have —
     * the failure is reported beside the content, not instead of it.
     */
    @Test
    fun `a failing refresh keeps the list and reports the failure`() = runTest(dispatcher) {
        val repository = FakeCompetitionsRepository(listOf(competition("a", "2026-03-01")))
        val viewModel = CompetitionsViewModel(repository)
        advanceUntilIdle()

        repository.failure = ApiError.Network(java.io.IOException("offline"))
        viewModel.refresh()
        advanceUntilIdle()

        val state = viewModel.uiState.value as CompetitionsUiState.Content
        assertEquals(listOf("a"), state.competitions.map { it.id })
        assertTrue(state.refreshFailed)
        assertTrue(!state.isRefreshing)

        // The snackbar fires once: acknowledging it clears the flag, so a
        // recomposition does not show the message again.
        viewModel.onMessageShown()
        assertTrue(!(viewModel.uiState.value as CompetitionsUiState.Content).refreshFailed)
    }

    /** A first load has no list to keep, so there the error takes the screen. */
    @Test
    fun `a failing first load still shows the error screen`() = runTest(dispatcher) {
        val viewModel = CompetitionsViewModel(
            FakeCompetitionsRepository(failure = ApiError.Forbidden),
        )
        advanceUntilIdle()
        viewModel.refresh()
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
    var competitions: List<Competition> = emptyList(),
    var failure: ApiError? = null,
) : CompetitionsRepository {
    override suspend fun list(): ApiResult<List<Competition>> =
        failure?.let { ApiResult.Failure(it) } ?: ApiResult.Success(competitions)

    override suspend fun scoreboard(competitionId: String): ApiResult<Scoreboard> =
        failure?.let { ApiResult.Failure(it) }
            ?: ApiResult.Success(Scoreboard(unit = "Ringe", highestWins = true, rows = emptyList()))
}
