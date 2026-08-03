package com.unefy.feature.competitions

import com.unefy.core.model.Competition
import com.unefy.core.model.Scoreboard
import com.unefy.core.network.ApiResult
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
import org.junit.Before
import org.junit.Test

/** The competition detail is the mirror row, live — nothing else. */
@OptIn(ExperimentalCoroutinesApi::class)
class CompetitionDetailViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `the mirrored competition renders`() = runTest(dispatcher) {
        val viewModel = viewModel(FakeMirrorRepository(listOf(competition("c-1"))))
        viewModel.load("c-1")
        advanceUntilIdle()

        val state = viewModel.uiState.value as CompetitionDetailUiState.Content
        assertEquals("c-1", state.competition.id)
    }

    @Test
    fun `an id the mirror does not carry stays Loading`() = runTest(dispatcher) {
        val viewModel = viewModel(FakeMirrorRepository(emptyList()))
        viewModel.load("c-404")
        advanceUntilIdle()

        assertEquals(CompetitionDetailUiState.Loading, viewModel.uiState.value)
    }

    /** A sync updating the row while the screen is open must reach it. */
    @Test
    fun `a mirror update lands in the state`() = runTest(dispatcher) {
        val repository = FakeMirrorRepository(listOf(competition("c-1")))
        val viewModel = viewModel(repository)
        viewModel.load("c-1")
        advanceUntilIdle()

        repository.rows.value = listOf(competition("c-1").copy(description = "Neu"))
        advanceUntilIdle()

        val state = viewModel.uiState.value as CompetitionDetailUiState.Content
        assertEquals("Neu", state.competition.description)
    }

    /** Subscribes on [TestScope.backgroundScope] — `WhileSubscribed` needs a collector. */
    private fun TestScope.viewModel(repository: CompetitionsRepository) =
        CompetitionDetailViewModel(repository).also { vm ->
            backgroundScope.launch { vm.uiState.collect {} }
        }

    private fun competition(id: String) = Competition(
        id = id,
        name = "Wettkampf $id",
        description = null,
        type = "competition",
        startDate = "2026-03-01",
        endDate = null,
        scoringUnit = "Ringe",
        scoringMode = "highest_wins",
        disciplines = listOf("Luftgewehr"),
    )
}

/** The mirror alone — the detail never talks to the network. */
private class FakeMirrorRepository(
    competitions: List<Competition>,
) : CompetitionsRepository {

    val rows = MutableStateFlow(competitions)

    override fun stream(): Flow<List<Competition>> = rows

    override fun hasSynced(): Flow<Boolean> = MutableStateFlow(true)

    override fun byIdStream(id: String): Flow<Competition?> =
        rows.map { list -> list.find { it.id == id } }

    override suspend fun scoreboard(
        competitionId: String,
        discipline: String?,
    ): ApiResult<Scoreboard> = error("the detail must not fetch the scoreboard")
}
