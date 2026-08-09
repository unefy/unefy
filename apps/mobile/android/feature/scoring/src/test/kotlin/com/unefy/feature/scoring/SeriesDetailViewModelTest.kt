package com.unefy.feature.scoring

import com.unefy.core.model.scoring.PlacedShot
import com.unefy.core.model.scoring.ShotSeriesDraft
import com.unefy.core.model.scoring.TargetGeometry
import com.unefy.core.model.scoring.TargetGeometrySeed
import com.unefy.core.network.ApiResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Before
import org.junit.Test

/**
 * Which source the detail screen may read.
 *
 * The screen is reachable from two lists. It used to read only the caller's own
 * history, so every row a board member opened from the club list answered
 * "Serie nicht gefunden" — the series was in the mirror, which nobody looked in.
 */
class SeriesDetailViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before fun setUp() = Dispatchers.setMain(dispatcher)

    @After fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `a series from the club mirror is found`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(
            mine = emptyList(),
            club = listOf(series("club-1", pending = false)),
        )
        val viewModel = viewModel(repository, "club-1")
        advanceUntilIdle()

        assertNotNull("the club mirror has to be searched too", viewModel.uiState.value)
        assertEquals("club-1", viewModel.uiState.value?.id)
    }

    @Test
    fun `a series from the own history is still found`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(
            mine = listOf(series("mine-1", pending = true)),
            club = emptyList(),
        )
        val viewModel = viewModel(repository, "mine-1")
        advanceUntilIdle()

        assertEquals("mine-1", viewModel.uiState.value?.id)
    }

    @Test
    fun `a series in both keeps the queue state of the own copy`() = runTest(dispatcher) {
        // A board member's own unsent series: the mirror's copy cannot know it
        // is still queued, so preferring it would hide the "not sent" marker.
        val repository = FakeDetailRepository(
            mine = listOf(series("both", pending = true)),
            club = listOf(series("both", pending = false)),
        )
        val viewModel = viewModel(repository, "both")
        advanceUntilIdle()

        assertEquals(true, viewModel.uiState.value?.pending)
    }

    @Test
    fun `an unknown id stays null`() = runTest(dispatcher) {
        val repository = FakeDetailRepository(mine = emptyList(), club = emptyList())
        val viewModel = viewModel(repository, "nope")
        advanceUntilIdle()

        assertEquals(null, viewModel.uiState.value)
    }

    private fun series(id: String, pending: Boolean) = ShotSeries(
        id = id,
        memberId = "m1",
        memberLabel = "Uwe Bauknecht",
        discipline = "GK Pistole 25m",
        targetTypeSlug = TargetGeometrySeed.PRECISION_25M.slug,
        caliberMm = 9.0,
        total = 87,
        innerTens = 2,
        groupingMm = 64.0,
        shots = listOf(PlacedShot("a", 0.02, -0.03, 10)),
        recordedAt = "2026-08-06T18:30:00Z",
        notes = null,
        pending = pending,
    )

    /** `WhileSubscribed` needs a collector, and `bind` has to run before it. */
    private fun TestScope.viewModel(repository: ScoringRepository, seriesId: String) =
        SeriesDetailViewModel(repository, NoDetailScans).also { vm ->
            vm.bind(seriesId)
            backgroundScope.launch { vm.uiState.collect {} }
        }
}

/** No photographs — this test is about which list the series comes from. */
private object NoDetailScans : SeriesScans {
    override fun load(seriesId: String, kind: ScanStore.Kind) = null

    override fun attach(seriesId: String) = Unit
}

private class FakeDetailRepository(
    mine: List<ShotSeries>,
    club: List<ShotSeries>,
) : ScoringRepository {

    private val mineFlow = MutableStateFlow(mine)
    private val clubFlow = MutableStateFlow(club)

    override fun myHistory(): Flow<List<ShotSeries>> = mineFlow

    override fun clubHistory(): Flow<List<ShotSeries>> = clubFlow

    override fun pendingCount(): Flow<Int> = MutableStateFlow(0)

    override suspend fun targetTypes(): List<TargetGeometry> = TargetGeometrySeed.ALL

    override suspend fun selectableMembers(): List<MemberOption> = emptyList()

    override suspend fun ownMember(): MemberOption? = null

    override suspend fun hasAttendanceOn(day: String): Boolean? = null

    override suspend fun record(
        draft: ShotSeriesDraft,
        memberId: String,
        memberLabel: String?,
        sessionId: String?,
        occurredOn: String,
        discipline: String?,
        recordedAt: String,
        notes: String?,
    ): String = "unused"

    override suspend fun correct(seriesId: String, draft: ShotSeriesDraft): ApiResult<Unit> =
        ApiResult.Success(Unit)

    override suspend fun delete(seriesId: String): ApiResult<Unit> = ApiResult.Success(Unit)

    override suspend fun refreshHistory(): ApiResult<Unit> = ApiResult.Success(Unit)

    override suspend fun drainQueue(): Int = 0

    override suspend fun discardPending(id: String) = Unit
}
