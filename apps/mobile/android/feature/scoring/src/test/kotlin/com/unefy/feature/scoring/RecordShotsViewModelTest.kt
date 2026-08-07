package com.unefy.feature.scoring

import com.unefy.core.model.scoring.PlacedShot
import com.unefy.core.model.scoring.ShotSeriesDraft
import com.unefy.core.model.scoring.TargetGeometry
import com.unefy.core.model.scoring.TargetGeometrySeed
import com.unefy.core.network.ApiResult
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf
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

/**
 * The recording screen has to be usable before, and without, the network.
 *
 * This is the whole reason the target catalog is compiled into the app. It was
 * still fetched in front of the user once, which left the screen on "loading
 * target" until the request finished — on a range with no signal, forever.
 */
class RecordShotsViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before fun setUp() = Dispatchers.setMain(dispatcher)

    @After fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `the target is usable before the catalog request finishes`() = runTest(dispatcher) {
        // A server that never answers — the basement case.
        val repository = FakeRepository(targets = CompletableDeferred())
        val viewModel = viewModel(repository)

        viewModel.start(
            sessionId = null,
            discipline = null,
            memberId = "m1",
            canPickMember = false,
            expectedShots = null,
        )

        val state = viewModel.uiState.value
        assertTrue("expected Content immediately, got $state", state is RecordShotsUiState.Content)
        state as RecordShotsUiState.Content
        assertEquals(TargetGeometrySeed.DEFAULT.slug, state.draft.geometry.slug)
        assertTrue("the picker must be populated too", state.targetTypes.isNotEmpty())
    }

    @Test
    fun `shots can be placed while the catalog is still loading`() = runTest(dispatcher) {
        val repository = FakeRepository(targets = CompletableDeferred())
        val viewModel = viewModel(repository)
        viewModel.start(null, null, "m1", canPickMember = false, expectedShots = null)

        val content = viewModel.uiState.value as RecordShotsUiState.Content
        viewModel.onDraftChange(content.draft.place("a", 0.0, 0.0))

        val after = viewModel.uiState.value as RecordShotsUiState.Content
        assertEquals(1, after.draft.shots.size)
        assertEquals(10, after.draft.total)
    }

    @Test
    fun `the server catalog replaces the seed once it arrives`() = runTest(dispatcher) {
        // Same slug, a corrected ring table — the reason the catalog is fetched
        // at all: a wrong diameter can be fixed without an app update.
        val corrected = TargetGeometrySeed.DEFAULT.copy(
            ringDiametersMm = TargetGeometrySeed.DEFAULT.ringDiametersMm.map { it + 2 },
        )
        val repository = FakeRepository(targets = CompletableDeferred(listOf(corrected)))
        val viewModel = viewModel(repository)

        viewModel.start(null, null, "m1", canPickMember = false, expectedShots = null)
        advanceUntilIdle()

        val state = viewModel.uiState.value as RecordShotsUiState.Content
        assertEquals(corrected.ringDiametersMm, state.draft.geometry.ringDiametersMm)
    }

    @Test
    fun `an unreachable catalog leaves the seed in place`() = runTest(dispatcher) {
        val repository = FakeRepository(targets = CompletableDeferred(emptyList()))
        val viewModel = viewModel(repository)

        viewModel.start(null, null, "m1", canPickMember = false, expectedShots = null)
        advanceUntilIdle()

        val state = viewModel.uiState.value as RecordShotsUiState.Content
        assertEquals(TargetGeometrySeed.ALL, state.targetTypes)
    }

    @Test
    fun `correcting a series keeps its shooter selected`() = runTest(dispatcher) {
        // The board can record for anyone, so the screen normally opens with no
        // shooter chosen. Correcting is not that case: the series already names
        // who fired it, and asking again every time invited picking the wrong
        // person and silently reassigning a result.
        val existing = recordedSeries(id = "s1", memberId = "m7", label = "Uwe Bauknecht")
        val repository = FakeRepository(
            targets = CompletableDeferred(TargetGeometrySeed.ALL),
            history = listOf(existing),
            members = listOf(MemberOption("m7", "Uwe Bauknecht"), MemberOption("m9", "Andere")),
        )
        val viewModel = viewModel(repository)

        viewModel.start(
            sessionId = null,
            discipline = null,
            memberId = null,
            canPickMember = true,
            expectedShots = null,
            seriesId = "s1",
        )
        advanceUntilIdle()

        val state = viewModel.uiState.value as RecordShotsUiState.Content
        assertEquals("m7", state.member?.id)
        assertEquals("Uwe Bauknecht", state.member?.label)
        assertEquals("the recorded shots must seed the draft", 3, state.draft.shots.size)
    }

    @Test
    fun `recording fresh still leaves the shooter to be picked`() = runTest(dispatcher) {
        // The counterpart: without a series to correct, the board must choose.
        val repository = FakeRepository(
            targets = CompletableDeferred(TargetGeometrySeed.ALL),
            members = listOf(MemberOption("m7", "Uwe Bauknecht")),
        )
        val viewModel = viewModel(repository)

        viewModel.start(
            sessionId = null,
            discipline = null,
            memberId = null,
            canPickMember = true,
            expectedShots = null,
        )
        advanceUntilIdle()

        val state = viewModel.uiState.value as RecordShotsUiState.Content
        assertEquals(null, state.member)
    }

    private fun recordedSeries(id: String, memberId: String, label: String) = ShotSeries(
        id = id,
        memberId = memberId,
        memberLabel = label,
        discipline = "GK Pistole 25m",
        targetTypeSlug = TargetGeometrySeed.PRECISION_25M.slug,
        caliberMm = 9.0,
        total = 28,
        innerTens = 0,
        groupingMm = 40.0,
        shots = listOf(
            PlacedShot("a", 0.0, 0.0, 10),
            PlacedShot("b", 0.1, 0.0, 10),
            PlacedShot("c", -0.2, 0.1, 8),
        ),
        recordedAt = "2026-08-07T08:30:00Z",
        notes = null,
        pending = false,
    )

    private fun viewModel(repository: ScoringRepository) =
        RecordShotsViewModel(repository, NoScans)
}

private class FakeRepository(
    private val targets: CompletableDeferred<List<TargetGeometry>>,
    private val history: List<ShotSeries> = emptyList(),
    private val members: List<MemberOption> = emptyList(),
) : ScoringRepository {
    override suspend fun targetTypes(): List<TargetGeometry> = targets.await()

    override suspend fun selectableMembers(): List<MemberOption> = members

    override suspend fun ownMember(): MemberOption? = MemberOption("m1", "Max Test")

    override suspend fun record(
        draft: ShotSeriesDraft,
        memberId: String,
        memberLabel: String?,
        sessionId: String?,
        occurredOn: String,
        discipline: String?,
        recordedAt: String,
        notes: String?,
    ): String = "id"

    override fun myHistory(): Flow<List<ShotSeries>> = flowOf(history)
    override fun pendingCount(): Flow<Int> = flowOf(0)
    override suspend fun refreshHistory(): ApiResult<Unit> = ApiResult.Success(Unit)
    override suspend fun drainQueue(): Int = 0
    override suspend fun correct(seriesId: String, draft: ShotSeriesDraft): ApiResult<Unit> =
        ApiResult.Success(Unit)

    override suspend fun delete(seriesId: String): ApiResult<Unit> = ApiResult.Success(Unit)

    override suspend fun discardPending(id: String) = Unit
}

/** No photographs on the JVM: `Bitmap` only exists on a device. */
private object NoScans : SeriesScans {
    override fun load(seriesId: String, kind: ScanStore.Kind) = null

    override fun attach(seriesId: String) = Unit
}
