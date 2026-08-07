package com.unefy.feature.attendance

import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import com.unefy.core.sync.ChangeHint
import com.unefy.core.testing.FakeCoordinator
import androidx.lifecycle.viewModelScope
import com.unefy.feature.attendance.nfc.CardEvent
import com.unefy.feature.attendance.nfc.CheckInApdu
import com.unefy.feature.attendance.nfc.NfcCheckInSignals
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancel
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * The code screen's life after the scan: confirmation must arrive, and — the
 * part that regressed — must also be able to leave again when the supervisor
 * takes the check-in back.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class MemberCodeViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    /** The test scheduler's virtual time, so delay() and the code agree on "now". */
    private fun clock() = AttendanceClock { dispatcher.scheduler.currentTime / 1_000 }

    private val signals = NfcCheckInSignals()

    /**
     * Runs [block] against a fresh view model and cancels its scope afterwards
     * — unconditionally. The tick loop never ends by design, and runTest's
     * cleanup would otherwise chase its rescheduled delays through virtual
     * time forever, pinning a CPU instead of finishing the test.
     */
    private inline fun withViewModel(
        repository: FakeAttendanceRepository,
        coordinator: FakeCoordinator = FakeCoordinator(),
        seedStore: FakeSeedStore = FakeSeedStore(),
        block: (MemberCodeViewModel) -> Unit,
    ) {
        val viewModel = MemberCodeViewModel(
            repository = repository,
            seedStore = seedStore,
            clock = clock(),
            nfcSignals = signals,
            coordinator = coordinator,
        )
        try {
            block(viewModel)
        } finally {
            viewModel.viewModelScope.cancel()
        }
    }

    @Test
    fun `a check-in appearing on the server confirms the screen`() = runTest(dispatcher) {
        val repository = FakeAttendanceRepository(
            ownCheckIn = ApiResult.Success(OwnCheckIn("Training", checkedInAtEpochSeconds = 0)),
        )
        withViewModel(repository) { viewModel ->
            runCurrent()

            assertEquals(MemberCodeUiState.Confirmed("Training"), viewModel.uiState.value)
        }
    }

    /**
     * Regression: the poll used to stop at the first confirmation, so a
     * check-in taken back at the scanner or in the web app left the member
     * staring at "Eingecheckt" for as long as the screen stayed open.
     */
    @Test
    fun `a check-in taken back on the server returns the screen to the code`() = runTest(dispatcher) {
        val repository = FakeAttendanceRepository(
            ownCheckIn = ApiResult.Success(OwnCheckIn("Training", checkedInAtEpochSeconds = 0)),
        )
        withViewModel(repository) { viewModel ->
            runCurrent()
            assertEquals(MemberCodeUiState.Confirmed("Training"), viewModel.uiState.value)

            repository.ownCheckIn = ApiResult.Success(null)
            advanceTimeBy(30_000)
            runCurrent()

            assertTrue(viewModel.uiState.value is MemberCodeUiState.Content)
        }
    }

    /**
     * Regression: the tick loop used to overwrite a tap's confirmation with the
     * next code within a second — permanently so when the scanner was offline
     * and the check-in only existed in its queue.
     */
    @Test
    fun `a queued tap confirmation stays up even though the server knows nothing`() =
        runTest(dispatcher) {
            val repository = FakeAttendanceRepository(ownCheckIn = ApiResult.Success(null))
            withViewModel(repository) { viewModel ->
                runCurrent()
                assertTrue(viewModel.uiState.value is MemberCodeUiState.Content)

                signals.publish(CardEvent.Read)
                runCurrent()
                assertEquals(MemberCodeUiState.Read, viewModel.uiState.value)

                signals.publish(CardEvent.Result(CheckInApdu.Outcome.QUEUED))
                runCurrent()
                advanceTimeBy(60_000)
                runCurrent()

                assertEquals(
                    MemberCodeUiState.Confirmed(sessionTitle = null),
                    viewModel.uiState.value,
                )
            }
        }

    /** A dead network is not a retraction — only a definite "no record" is. */
    @Test
    fun `a failing poll does not take a confirmation back`() = runTest(dispatcher) {
        val repository = FakeAttendanceRepository(
            ownCheckIn = ApiResult.Success(OwnCheckIn("Training", checkedInAtEpochSeconds = 0)),
        )
        withViewModel(repository) { viewModel ->
            runCurrent()
            assertEquals(MemberCodeUiState.Confirmed("Training"), viewModel.uiState.value)

            repository.ownCheckIn = ApiResult.Failure(ApiError.Network(IOException("offline")))
            advanceTimeBy(60_000)
            runCurrent()

            assertEquals(MemberCodeUiState.Confirmed("Training"), viewModel.uiState.value)
        }
    }

    /**
     * The server-side instant path, for the case NFC cannot serve: a camera scan.
     *
     * What makes this worth the machinery is the timing. The poll reads again two
     * seconds after the last one, so a scan just after a read left the member
     * holding a code that had already been accepted — long enough to look broken
     * and to make the supervisor scan again. Here the news arrives 900 ms in, well
     * before the next scheduled read, and the screen turns over at once.
     */
    @Test
    fun `a signal confirms the screen before the next poll would`() = runTest(dispatcher) {
        val repository = FakeAttendanceRepository(ownCheckIn = ApiResult.Success(null))
        val coordinator = FakeCoordinator()
        withViewModel(repository, coordinator) { viewModel ->
            runCurrent()
            assertTrue(viewModel.uiState.value is MemberCodeUiState.Content)

            // The supervisor scans the code on their own phone…
            repository.ownCheckIn =
                ApiResult.Success(OwnCheckIn("Training", checkedInAtEpochSeconds = 0))
            advanceTimeBy(900)
            runCurrent()
            // …not yet: 900 ms in, the poll's next read is still 1.1 s away.
            assertTrue(viewModel.uiState.value is MemberCodeUiState.Content)

            coordinator.hints.tryEmit(
                ChangeHint(entity = CHECK_IN_SIGNAL, id = "record-1", op = "upsert"),
            )
            runCurrent()

            assertEquals(MemberCodeUiState.Confirmed("Training"), viewModel.uiState.value)
        }
    }

    /**
     * The frame is a doorbell, not evidence.
     *
     * It carries no authorisation and this app never checks who it was addressed
     * to — the server did that. So a hint may only ever cause a re-read of the
     * endpoint scoped to this account. If the answer is "no check-in", the screen
     * keeps showing the code, however loudly the stream rang.
     */
    @Test
    fun `a signal alone confirms nothing`() = runTest(dispatcher) {
        val repository = FakeAttendanceRepository(ownCheckIn = ApiResult.Success(null))
        val coordinator = FakeCoordinator()
        withViewModel(repository, coordinator) { viewModel ->
            runCurrent()

            coordinator.hints.tryEmit(
                ChangeHint(entity = CHECK_IN_SIGNAL, id = "record-1", op = "upsert"),
            )
            runCurrent()

            assertTrue(viewModel.uiState.value is MemberCodeUiState.Content)
        }
    }

    /** Hints about everything else in the club are none of this screen's business. */
    @Test
    fun `a hint about another collection is ignored`() = runTest(dispatcher) {
        val repository = FakeAttendanceRepository(ownCheckIn = ApiResult.Success(null))
        val coordinator = FakeCoordinator()
        withViewModel(repository, coordinator) { viewModel ->
            runCurrent()
            repository.reads = 0

            coordinator.hints.tryEmit(ChangeHint(entity = "members", id = "m1", op = "upsert"))
            runCurrent()

            assertEquals(0, repository.reads)
        }
    }

    /**
     * Regression, and the reported one: "the app has no QR code offline".
     *
     * A seed expires daily, so at a basement range the stored one is usually
     * out of date — and the screen used to fetch a replacement *before* showing
     * anything. With no connection that request does not fail, it hangs until
     * the timeout, and the member holds out a blank screen for ten seconds.
     * The stale code was there the whole time and verifies for two more periods.
     */
    @Test
    fun `an expired stored seed shows a code without waiting for the network`() =
        runTest(dispatcher) {
            val repository = FakeAttendanceRepository(
                ownCheckIn = ApiResult.Failure(ApiError.Network(IOException("offline"))),
                seedResult = { awaitCancellation() },
            )
            withViewModel(repository, seedStore = FakeSeedStore(expiresAtEpochSeconds = 0)) {
                runCurrent()

                val state = it.uiState.value
                assertTrue("still $state", state is MemberCodeUiState.Content)
                // Said out loud on screen, because it might not verify.
                assertTrue((state as MemberCodeUiState.Content).seedStale)
            }
        }

    /** And once a connection does answer, the loop moves onto the fresh seed. */
    @Test
    fun `a seed fetched in the background replaces the stale one`() = runTest(dispatcher) {
        val fresh = AttendanceSeed(
            memberRef = "MNOPQRSTUVWX2345",
            seed = "FRESHSEED12345",
            tenantId = "tenant-1",
            expiresAtEpochSeconds = Long.MAX_VALUE,
        )
        val store = FakeSeedStore(expiresAtEpochSeconds = 0)
        // Answers only when the test lets it, so the two moments stay apart:
        // the stale code is on screen first, the fresh one replaces it after.
        val answered = CompletableDeferred<ApiResult<AttendanceSeed>>()
        val repository = FakeAttendanceRepository(
            ownCheckIn = ApiResult.Success(null),
            seedResult = { answered.await() },
        )
        withViewModel(repository, seedStore = store) {
            runCurrent()
            assertTrue((it.uiState.value as MemberCodeUiState.Content).seedStale)

            answered.complete(ApiResult.Success(fresh))
            advanceTimeBy(1_000)
            runCurrent()

            val state = it.uiState.value
            assertTrue("still $state", state is MemberCodeUiState.Content)
            assertTrue(!(state as MemberCodeUiState.Content).seedStale)
            // Kept, or the next cold start would be stale again.
            assertEquals(fresh, store.written)
        }
    }

    @Test
    fun `a rejected tap returns the screen to the code`() = runTest(dispatcher) {
        val repository = FakeAttendanceRepository(ownCheckIn = ApiResult.Success(null))
        withViewModel(repository) { viewModel ->
            runCurrent()

            signals.publish(CardEvent.Read)
            runCurrent()
            signals.publish(CardEvent.Result(CheckInApdu.Outcome.REJECTED))
            runCurrent()
            advanceTimeBy(2_000)
            runCurrent()

            assertTrue(viewModel.uiState.value is MemberCodeUiState.Content)
        }
    }
}

class FakeSeedStore(expiresAtEpochSeconds: Long = Long.MAX_VALUE) : SeedStore {
    override val cached: AttendanceSeed? = null

    /** The last seed handed to [write], so a test can see a refresh persisted. */
    var written: AttendanceSeed? = null
        private set

    private val stored = AttendanceSeed(
        memberRef = "MNOPQRSTUVWX2345",
        seed = "SEEDVALUE12345",
        tenantId = "tenant-1",
        expiresAtEpochSeconds = expiresAtEpochSeconds,
    )

    override suspend fun read() = stored

    override suspend fun write(seed: AttendanceSeed) {
        written = seed
    }

    override suspend fun clear() = Unit
}

private class FakeAttendanceRepository(
    var ownCheckIn: ApiResult<OwnCheckIn?>,
    /** A dead connection is a call that does not answer, not one that returns. */
    private val seedResult: suspend () -> ApiResult<AttendanceSeed> = {
        error("the stored seed should have answered")
    },
) : AttendanceRepository {
    /** Counted, so a test can assert that nothing was read at all. */
    var reads = 0

    override suspend fun latestOwnCheckIn(): ApiResult<OwnCheckIn?> {
        reads++
        return ownCheckIn
    }

    override suspend fun seed(): ApiResult<AttendanceSeed> = seedResult()

    override suspend fun openSessions() = error("unused")

    override suspend fun scan(
        sessionId: String,
        code: String,
        installId: String?,
        staffDeviceId: String?,
        checkedInAt: String?,
    ) = error("unused")

    override suspend fun checkInManually(
        sessionId: String,
        memberId: String?,
        guestName: String?,
        checkedInAt: String?,
        clientId: String?,
    ) = error("unused")

    override suspend fun createSession(title: String, opensAt: String, closesAt: String) =
        error("unused")

    override suspend fun members(search: String?) = error("unused")

    override suspend fun sessionRecords(sessionId: String) = error("unused")

    override suspend fun deleteRecord(recordId: String, reason: String?) = error("unused")

    override suspend fun myRangeDays() = error("unused")

    override suspend fun createSelfEntry(occurredOn: String, location: String) = error("unused")

    override suspend fun deleteSelfEntry(recordId: String) = error("unused")

    override suspend fun todaysEvents(startIso: String, endIso: String) = error("unused")

    override suspend fun openSessionForEvent(eventId: String) = error("unused")
}
