package com.unefy.feature.competitions

import com.unefy.core.model.Competition
import com.unefy.core.model.Scoreboard
import com.unefy.core.model.ScoreboardRow
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
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
 * The competition list reads the local mirror; the scoreboard stays an online
 * aggregate and keeps its own tests below.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class CompetitionsViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `an unsynced mirror is Loading, not empty`() = runTest(dispatcher) {
        val viewModel = viewModel(FakeCompetitionsRepository(hasSynced = false))
        advanceUntilIdle()

        assertEquals(CompetitionsUiState.Loading, viewModel.uiState.value)
    }

    @Test
    fun `a synced but empty mirror is Content, not Loading`() = runTest(dispatcher) {
        val viewModel = viewModel(FakeCompetitionsRepository())
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertTrue(state is CompetitionsUiState.Content)
        assertEquals(
            emptyList<Competition>(),
            (state as CompetitionsUiState.Content).competitions,
        )
    }

    /** The point of the mirror: a background sync reaches the screen unasked. */
    @Test
    fun `a row appearing in the mirror reaches the screen unasked`() = runTest(dispatcher) {
        val repository = FakeCompetitionsRepository(listOf(competition("1")))
        val viewModel = viewModel(repository)
        advanceUntilIdle()

        repository.rows.value = listOf(competition("1"), competition("2"))
        advanceUntilIdle()

        val state = viewModel.uiState.value as CompetitionsUiState.Content
        assertEquals(listOf("1", "2"), state.competitions.map { it.id })
    }

    @Test
    fun `a sync failure keeps the list and reports why it is stale`() = runTest(dispatcher) {
        val coordinator = FakeCoordinator()
        val viewModel = viewModel(FakeCompetitionsRepository(listOf(competition("1"))), coordinator)
        advanceUntilIdle()

        coordinator.status.value = SyncStatus.Failed(ApiError.Network(IOException("no signal")))
        advanceUntilIdle()

        val state = viewModel.uiState.value as CompetitionsUiState.Content
        assertEquals(listOf("1"), state.competitions.map { it.id })
        assertTrue(state.staleBecause is ApiError.Network)

        coordinator.status.value = SyncStatus.Idle
        advanceUntilIdle()
        assertNull((viewModel.uiState.value as CompetitionsUiState.Content).staleBecause)
    }

    @Test
    fun `a sync failure with an empty mirror is a Failure`() = runTest(dispatcher) {
        val coordinator = FakeCoordinator(SyncStatus.Failed(ApiError.Network(IOException())))
        val viewModel = viewModel(FakeCompetitionsRepository(hasSynced = false), coordinator)
        advanceUntilIdle()

        assertTrue(viewModel.uiState.value is CompetitionsUiState.Failure)
    }

    @Test
    fun `refresh asks the coordinator to sync now`() = runTest(dispatcher) {
        val coordinator = FakeCoordinator()
        val viewModel = viewModel(FakeCompetitionsRepository(), coordinator)
        advanceUntilIdle()

        viewModel.refresh()
        advanceUntilIdle()

        assertEquals(listOf("competitions"), coordinator.syncedNow)
    }

    @Test
    fun `a second refresh while one is running is ignored`() = runTest(dispatcher) {
        val coordinator = FakeCoordinator(blockSync = true)
        val viewModel = viewModel(FakeCompetitionsRepository(), coordinator)
        advanceUntilIdle()

        viewModel.refresh()
        viewModel.refresh()
        viewModel.refresh()
        advanceUntilIdle()

        assertEquals(1, coordinator.syncedNow.size)
    }

    // ------------------------------------------------------------------
    // Scoreboard — online, unchanged by the mirror work.
    // ------------------------------------------------------------------

    @Test
    fun `the scoreboard loads for its competition`() = runTest(dispatcher) {
        val repository = FakeCompetitionsRepository(
            scoreboard = Scoreboard(
                unit = "Ringe",
                highestWins = true,
                rows = listOf(
                    ScoreboardRow(
                        rank = 1,
                        memberId = "m1",
                        memberName = "Anna Bauer",
                        totalScore = 291.0,
                        bestScore = 98.0,
                        averageScore = 97.0,
                        entryCount = 3,
                    ),
                ),
            ),
        )
        val viewModel = ScoreboardViewModel(repository)

        viewModel.load("c-1")
        advanceUntilIdle()

        val state = viewModel.uiState.value as ScoreboardUiState.Content
        assertEquals("Anna Bauer", state.scoreboard.rows.single().memberName)
    }

    @Test
    fun `selecting a discipline reloads the board filtered`() = runTest(dispatcher) {
        val repository = FakeCompetitionsRepository(
            competitions = listOf(
                competition("c-1").copy(disciplines = listOf("Luftgewehr", "KK-Pistole")),
            ),
            scoreboard = Scoreboard(unit = "Ringe", highestWins = true, rows = emptyList()),
        )
        val viewModel = scoreboardViewModel(repository)

        viewModel.load("c-1")
        advanceUntilIdle()
        assertEquals(listOf("Luftgewehr", "KK-Pistole"), viewModel.disciplines.value)

        viewModel.selectDiscipline("Luftgewehr")
        advanceUntilIdle()
        assertEquals("Luftgewehr", viewModel.selectedDiscipline.value)

        viewModel.selectDiscipline(null)
        advanceUntilIdle()

        assertEquals(listOf(null, "Luftgewehr", null), repository.scoreboardRequests)
    }

    @Test
    fun `reselecting the current discipline does not reload`() = runTest(dispatcher) {
        val repository = FakeCompetitionsRepository(
            scoreboard = Scoreboard(unit = "Ringe", highestWins = true, rows = emptyList()),
        )
        val viewModel = scoreboardViewModel(repository)

        viewModel.load("c-1")
        advanceUntilIdle()

        viewModel.selectDiscipline(null)
        advanceUntilIdle()

        assertEquals(listOf<String?>(null), repository.scoreboardRequests)
    }

    @Test
    fun `a failing scoreboard is an error`() = runTest(dispatcher) {
        val repository = FakeCompetitionsRepository(scoreboardFailure = ApiError.Forbidden)
        val viewModel = ScoreboardViewModel(repository)

        viewModel.load("c-1")
        advanceUntilIdle()

        assertTrue(viewModel.uiState.value is ScoreboardUiState.Failure)
    }

    /** [ScoreboardViewModel.disciplines] is `WhileSubscribed` — it needs a collector. */
    private fun TestScope.scoreboardViewModel(repository: CompetitionsRepository) =
        ScoreboardViewModel(repository).also { vm ->
            backgroundScope.launch { vm.disciplines.collect {} }
        }

    /** Subscribes on [TestScope.backgroundScope] — `WhileSubscribed` needs a collector. */
    private fun TestScope.viewModel(
        repository: CompetitionsRepository,
        coordinator: FakeCoordinator = FakeCoordinator(),
    ) = CompetitionsViewModel(repository, coordinator).also { vm ->
        backgroundScope.launch { vm.uiState.collect {} }
    }

    private fun competition(id: String) = Competition(
        id = id,
        name = "Wettkampf $id",
        description = null,
        type = null,
        startDate = "2026-01-0$id",
        endDate = null,
        scoringUnit = "Ringe",
        scoringMode = "highest_wins",
        disciplines = emptyList(),
    )
}

/** Stands in for Room ([rows]) and the scoreboard endpoint. */
private class FakeCompetitionsRepository(
    competitions: List<Competition> = emptyList(),
    private val hasSynced: Boolean = true,
    private val scoreboard: Scoreboard? = null,
    private val scoreboardFailure: ApiError? = null,
) : CompetitionsRepository {

    val rows = MutableStateFlow(competitions)

    /** The discipline of each scoreboard call, null for the combined board. */
    val scoreboardRequests = mutableListOf<String?>()

    override fun stream(): Flow<List<Competition>> = rows

    override fun hasSynced(): Flow<Boolean> = MutableStateFlow(hasSynced)

    override fun byIdStream(id: String): Flow<Competition?> =
        rows.map { list -> list.find { it.id == id } }

    override suspend fun scoreboard(
        competitionId: String,
        discipline: String?,
    ): ApiResult<Scoreboard> {
        scoreboardRequests += discipline
        return scoreboardFailure?.let { ApiResult.Failure(it) }
            ?: ApiResult.Success(requireNotNull(scoreboard))
    }
}
