package com.unefy.core.sync

import com.unefy.core.network.ApiError
import java.io.IOException
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonElement
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * When the coordinator syncs, and how often.
 *
 * The interesting behaviour is all about *not* syncing: not once per hint, not
 * again after a refusal, not for a collection this app does not mirror. Each of
 * those, left out, gives a working app that talks to the server far more than it
 * needs to — the kind of fault nobody notices until it is somebody's mobile data.
 *
 * The engine is faked here rather than driven over a mock HTTP engine. Not for
 * speed: Ktor runs its pipeline on its own dispatchers, so `advanceUntilIdle`
 * would return while a request was still in flight and every assertion below
 * would be a race. What the drain does with a page is `SyncEngineTest`'s subject.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class SyncCoordinatorTest {

    private val hints = MutableSharedFlow<ChangeHint>()
    private val online = MutableStateFlow(true)
    private val engine = FakeEngine()

    private val coordinator = DefaultSyncCoordinator(
        collections = setOf(NoopCollection()),
        engine = engine,
        changeStream = ChangeStream { hints },
        connectivity = ConnectivityMonitor { online },
    )

    /**
     * The doorbell, re-emitted for listeners that are not mirrors.
     *
     * The member's check-in screen needs the news itself, not a drain: a drain is
     * held back until the server's cursor watermark has moved, which is slower than
     * the poll it replaces. Routed through here so the app keeps one stream instead
     * of opening a second socket to hear the same frames.
     */
    @Test
    fun `an addressed hint reaches a listener`() = runTest {
        val job = launch { coordinator.run() }
        advanceUntilIdle()

        val heard = mutableListOf<ChangeHint>()
        val listener = launch { coordinator.signals("check-ins").collect { heard += it } }
        advanceUntilIdle()

        hints.emit(ChangeHint(entity = "check-ins", id = "record-1", op = "upsert"))
        advanceUntilIdle()

        assertEquals(listOf("record-1"), heard.map { it.id })
        listener.cancelAndJoin()
        job.cancelAndJoin()
    }

    @Test
    fun `a listener hears only its own entity`() = runTest {
        val job = launch { coordinator.run() }
        advanceUntilIdle()

        val heard = mutableListOf<ChangeHint>()
        val listener = launch { coordinator.signals("check-ins").collect { heard += it } }
        advanceUntilIdle()

        hints.emit(ChangeHint(entity = "members", id = "m1", op = "upsert"))
        advanceUntilIdle()

        assertTrue(heard.isEmpty())
        listener.cancelAndJoin()
        job.cancelAndJoin()
    }

    /**
     * An addressed hint is not a collection, and must not be treated as one.
     *
     * `check-ins` has no `/sync/check-ins` to drain and must never get one — a
     * member may know about their own attendance, not about everybody else's. The
     * coordinator's existing "unknown names are ordinary" rule is what makes that
     * safe, and this pins it.
     */
    @Test
    fun `an addressed hint drains nothing`() = runTest {
        val job = launch { coordinator.run() }
        advanceUntilIdle()
        val baseline = engine.syncs

        hints.emit(ChangeHint(entity = "check-ins", id = "record-1", op = "upsert"))
        advanceTimeBy(10_000)

        assertEquals(baseline, engine.syncs)
        job.cancelAndJoin()
    }

    @Test
    fun `a burst of hints about one collection produces one sync`() = runTest {
        val job = launch { coordinator.run() }
        advanceUntilIdle()
        val baseline = engine.syncs

        repeat(5) { hints.emit(ChangeHint(entity = "members", id = "m$it")) }
        // Only past the coalescing window, not past the settle delay — the second
        // drain that follows a hint is the next test's subject.
        advanceTimeBy(1_000)

        assertEquals(baseline + 1, engine.syncs)
        job.cancelAndJoin()
    }

    /**
     * The bug this caught on a real device: a member renamed in the web app never
     * appeared on the phone. Not late — never.
     *
     * The hint is published after commit, but the sync query refuses to read
     * anything newer than `now() - CURSOR_SAFETY_LAG`. The drain a quarter-second
     * after the doorbell therefore comes back empty, stores the cursor and reports
     * success, and nothing asks again. A hint has to schedule a second drain for
     * after the server will admit the change.
     */
    @Test
    fun `a hint schedules a second drain for after the server's safety lag`() = runTest {
        val job = launch { coordinator.run() }
        advanceUntilIdle()
        val baseline = engine.syncs

        hints.emit(ChangeHint(entity = "members", id = "m1"))
        advanceTimeBy(1_000)
        assertEquals("the immediate drain", baseline + 1, engine.syncs)

        // Past the server's five-second watermark.
        advanceTimeBy(7_000)
        assertEquals("the drain that actually delivers", baseline + 2, engine.syncs)

        job.cancelAndJoin()
    }

    /** And it stops there — the follow-up must not schedule a follow-up of its own. */
    @Test
    fun `the second drain does not schedule a third`() = runTest {
        val job = launch { coordinator.run() }
        advanceUntilIdle()
        val baseline = engine.syncs

        hints.emit(ChangeHint(entity = "members", id = "m1"))
        advanceTimeBy(30_000)

        assertEquals(baseline + 2, engine.syncs)
        job.cancelAndJoin()
    }

    /**
     * Only hints need it. Coming online has no just-committed change waiting behind
     * the watermark, so a second drain there would be a wasted request on every
     * app start.
     */
    @Test
    fun `coming online does not schedule a second drain`() = runTest {
        online.value = false
        val job = launch { coordinator.run() }
        advanceUntilIdle()

        online.value = true
        advanceTimeBy(30_000)

        assertEquals(1, engine.syncs)
        job.cancelAndJoin()
    }

    /** Coming online is itself a reason to sync — it is what fills a fresh install. */
    @Test
    fun `becoming online triggers a sync`() = runTest {
        online.value = false
        val job = launch { coordinator.run() }
        advanceUntilIdle()
        assertEquals(0, engine.syncs)

        online.value = true
        advanceUntilIdle()

        assertEquals(1, engine.syncs)
        job.cancelAndJoin()
    }

    /**
     * The server streams hints for every collection it knows; this app mirrors one
     * of them so far. The rest have to be dropped without a round trip.
     */
    @Test
    fun `a hint for a collection this app does not mirror is ignored`() = runTest {
        val job = launch { coordinator.run() }
        advanceUntilIdle()
        val baseline = engine.syncs

        hints.emit(ChangeHint(entity = "dues", id = "d1"))
        advanceUntilIdle()

        assertEquals(baseline, engine.syncs)
        job.cancelAndJoin()
    }

    /**
     * A plain member may not mirror the member list, and that answer cannot change
     * while they are signed in. Asking again on every hint would be one request per
     * change in the whole club, forever, for a 403.
     */
    @Test
    fun `a refused collection is asked once and then left alone`() = runTest {
        engine.outcome = SyncOutcome.NotPermitted
        val job = launch { coordinator.run() }
        advanceUntilIdle()

        assertEquals(SyncStatus.NotPermitted, coordinator.status("members").first())
        val baseline = engine.syncs

        repeat(3) { hints.emit(ChangeHint(entity = "members")) }
        advanceUntilIdle()

        assertEquals(baseline, engine.syncs)
        job.cancelAndJoin()
    }

    /** A failure is worth retrying, so unlike a refusal it must not latch. */
    @Test
    fun `a failed sync is retried on the next hint`() = runTest {
        engine.outcome = SyncOutcome.Failed(ApiError.Network(IOException("no signal")))
        val job = launch { coordinator.run() }
        advanceUntilIdle()

        assertTrue(coordinator.status("members").first() is SyncStatus.Failed)
        val baseline = engine.syncs

        hints.emit(ChangeHint(entity = "members"))
        // Past the coalescing window only, so this counts the immediate drain and
        // not the settle drain that follows every hint.
        advanceTimeBy(1_000)

        assertEquals(baseline + 1, engine.syncs)
        job.cancelAndJoin()
    }

    @Test
    fun `status returns to idle after a successful sync`() = runTest {
        val job = launch { coordinator.run() }
        advanceUntilIdle()

        assertEquals(SyncStatus.Idle, coordinator.status("members").first())
        job.cancelAndJoin()
    }

    /**
     * A screen needs to see the sync happening, or pull-to-refresh has no spinner
     * to show and the gesture reads as broken.
     */
    @Test
    fun `status reports syncing while a drain is in flight`() = runTest {
        engine.block = true
        val job = launch { coordinator.run() }
        advanceUntilIdle()

        assertEquals(SyncStatus.Syncing, coordinator.status("members").first())

        job.cancelAndJoin()
    }

    /**
     * The coordinator is a singleton and outlives the account. A board member
     * signing in after a plain member must not inherit the plain member's refusal.
     */
    @Test
    fun `sign-out forgets a latched refusal`() = runTest {
        engine.outcome = SyncOutcome.NotPermitted
        val job = launch { coordinator.run() }
        advanceUntilIdle()
        assertEquals(SyncStatus.NotPermitted, coordinator.status("members").first())

        coordinator.forgetStatuses()

        assertEquals(SyncStatus.Idle, coordinator.status("members").first())
        job.cancelAndJoin()
    }

    /** A refresh gesture asks directly rather than waiting for a hint. */
    @Test
    fun `an explicit request syncs`() = runTest {
        online.value = false
        val job = launch { coordinator.run() }
        advanceUntilIdle()
        assertEquals(0, engine.syncs)

        coordinator.request("members")
        advanceUntilIdle()

        assertEquals(1, engine.syncs)
        job.cancelAndJoin()
    }
}

private class FakeEngine : SyncEngine {
    var syncs = 0
    var outcome: SyncOutcome = SyncOutcome.UpToDate

    /** Never returns, so a test can observe the in-flight status. */
    var block = false

    override suspend fun sync(collection: SyncCollection): SyncOutcome {
        syncs++
        if (block) kotlinx.coroutines.awaitCancellation()
        return outcome
    }
}

private class NoopCollection : SyncCollection {
    override val name = "members"
    override suspend fun apply(
        changed: List<JsonElement>,
        deleted: List<String>,
        generation: Long,
    ) = Unit

    override suspend fun sweep(generation: Long) = Unit
    override suspend fun clear() = Unit
}
