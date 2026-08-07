package com.unefy.feature.scoring

import com.unefy.core.model.scoring.PlacedShot
import com.unefy.core.model.scoring.ShotSeriesDraft
import com.unefy.core.model.scoring.TargetGeometrySeed
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.Flow
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
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * The offline promise, exercised end to end through the repository interface.
 *
 * What has to hold: a series recorded without a network is visible immediately
 * and marked as unsent, and it stops being marked once it reaches the server.
 */
class ShotHistoryViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before fun setUp() = Dispatchers.setMain(dispatcher)

    @After fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `a series recorded offline shows up immediately as pending`() = runTest(dispatcher) {
        val repository = FakeScoringRepository(online = false)
        repository.recordSeries()

        val viewModel = viewModel(repository)
        advanceUntilIdle()

        val state = viewModel.uiState.value as ShotHistoryUiState.Content
        assertEquals(1, state.series.size)
        assertTrue(state.series[0].pending)
        assertEquals(1, state.pendingCount)
    }

    @Test
    fun `the queue drains once the network is back`() = runTest(dispatcher) {
        val repository = FakeScoringRepository(online = false)
        repository.recordSeries()

        repository.online = true
        val viewModel = viewModel(repository)
        advanceUntilIdle()

        val state = viewModel.uiState.value as ShotHistoryUiState.Content
        assertEquals(0, state.pendingCount)
        assertEquals(1, state.series.size)
        assertTrue("series should no longer be pending", !state.series[0].pending)
    }

    @Test
    fun `an empty history is Content, not Loading`() = runTest(dispatcher) {
        val viewModel = viewModel(FakeScoringRepository(online = true))
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertTrue("expected Content, got $state", state is ShotHistoryUiState.Content)
        assertEquals(0, (state as ShotHistoryUiState.Content).series.size)
    }

    /** `WhileSubscribed` needs a collector or the flow never starts. */
    private fun TestScope.viewModel(repository: ScoringRepository) =
        ShotHistoryViewModel(repository).also { vm ->
            backgroundScope.launch { vm.uiState.collect {} }
        }
}

/**
 * A repository with a switchable network, modelling the queue-and-cache split
 * the real one has: recording always lands in the queue, draining moves it into
 * the cache, and only a drain can do that.
 */
private class FakeScoringRepository(var online: Boolean) : ScoringRepository {

    private val queued = MutableStateFlow<List<ShotSeries>>(emptyList())
    private val cached = MutableStateFlow<List<ShotSeries>>(emptyList())

    fun recordSeries(id: String = "series-1") {
        queued.value = queued.value + series(id, pending = true)
    }

    override suspend fun targetTypes() = TargetGeometrySeed.ALL

    override suspend fun selectableMembers(): List<MemberOption> = emptyList()

    override suspend fun ownMember(): MemberOption? = null

    override suspend fun record(
        draft: ShotSeriesDraft,
        memberId: String,
        memberLabel: String?,
        sessionId: String?,
        occurredOn: String,
        discipline: String?,
        recordedAt: String,
        notes: String?,
    ): String {
        val id = "series-${queued.value.size + 1}"
        recordSeries(id)
        return id
    }

    override fun myHistory(): Flow<List<ShotSeries>> =
        kotlinx.coroutines.flow.combine(queued, cached, ::mergeSeries)

    override fun pendingCount(): Flow<Int> = queued.map { it.size }

    override suspend fun refreshHistory(): ApiResult<Unit> =
        if (online) ApiResult.Success(Unit) else ApiResult.Failure(ApiError.Network(IllegalStateException("offline")))

    override suspend fun drainQueue(): Int {
        if (!online) return 0
        val sending = queued.value
        cached.value = cached.value + sending.map { it.copy(pending = false) }
        queued.value = emptyList()
        return sending.size
    }

    override suspend fun discardPending(id: String) {
        queued.value = queued.value.filterNot { it.id == id }
    }

    /** Queued series are dropped locally; sent ones are withdrawn on the server. */
    override suspend fun delete(seriesId: String): ApiResult<Unit> {
        if (queued.value.any { it.id == seriesId }) {
            queued.value = queued.value.filterNot { it.id == seriesId }
            return ApiResult.Success(Unit)
        }
        if (!online) {
            return ApiResult.Failure(ApiError.Network(IllegalStateException("offline")))
        }
        cached.value = cached.value.filterNot { it.id == seriesId }
        return ApiResult.Success(Unit)
    }

    /**
     * Rewrites the queued copy, mirroring the real one: a series still waiting
     * to be sent is corrected locally, a series already at the server needs the
     * network.
     */
    override suspend fun correct(seriesId: String, draft: ShotSeriesDraft): ApiResult<Unit> {
        val queuedSeries = queued.value.firstOrNull { it.id == seriesId }
        if (queuedSeries != null) {
            queued.value = queued.value.map {
                if (it.id == seriesId) it.copy(shots = draft.shots) else it
            }
            return ApiResult.Success(Unit)
        }
        if (!online) {
            return ApiResult.Failure(ApiError.Network(IllegalStateException("offline")))
        }
        cached.value = cached.value.map {
            if (it.id == seriesId) it.copy(shots = draft.shots) else it
        }
        return ApiResult.Success(Unit)
    }

    private fun series(id: String, pending: Boolean) = ShotSeries(
        id = id,
        memberId = "m1",
        memberLabel = "Max Test",
        discipline = "GK Pistole 25m",
        targetTypeSlug = TargetGeometrySeed.PRECISION_25M.slug,
        caliberMm = 9.0,
        total = 87,
        innerTens = 2,
        groupingMm = 64.0,
        shots = listOf(PlacedShot("a", 0.02, -0.03, 10)),
        recordedAt = "2026-08-05T18:30:00Z",
        notes = null,
        pending = pending,
    )
}
