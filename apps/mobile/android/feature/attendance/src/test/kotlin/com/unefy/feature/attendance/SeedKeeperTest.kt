package com.unefy.feature.attendance

import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import com.unefy.core.sync.ConnectivityMonitor
import java.io.IOException
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * The seed has to be fetched where the connection is, not where the screen is.
 *
 * Everything here is about *when* a request is made: one when it is needed,
 * none when it is not, and none at all for somebody who is not signed in.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class SeedKeeperTest {

    private val dispatcher = StandardTestDispatcher()
    private val online = MutableStateFlow(false)
    private val signedIn = MutableStateFlow(true)
    private val store = KeeperSeedStore()
    private val repository = KeeperRepository()

    private var scheduled = 0

    private fun keeper(now: Long = 0) = SeedKeeper(
        repository = repository,
        seedStore = store,
        clock = { now },
        connectivity = ConnectivityMonitor { online },
        auth = SignedInSource { signedIn },
        scheduler = { scheduled++ },
    )

    /** Runs the keeper for the duration of [block], then stops it. */
    private fun TestScope.running(keeper: SeedKeeper, block: () -> Unit) {
        val job = launch { keeper.run() }
        try {
            runCurrent()
            block()
        } finally {
            job.cancel()
        }
    }

    @Test
    fun `an expired seed is replaced as soon as there is a connection`() = runTest(dispatcher) {
        store.stored = seed(expiresAt = 0)

        running(keeper(now = 10)) {
            assertEquals(0, repository.calls)

            online.value = true
            runCurrent()

            assertEquals(1, repository.calls)
            assertEquals(FETCHED, store.stored)
        }
    }

    /**
     * The whole point: a phone that never opens the check-in screen still has a
     * seed when it finally does, at the range, with no signal. Without this the
     * only fetch in the app was that screen's own.
     */
    @Test
    fun `a device that has never had a seed gets one`() = runTest(dispatcher) {
        store.stored = null

        running(keeper()) {
            online.value = true
            runCurrent()

            assertEquals(FETCHED, store.stored)
        }
    }

    /** A seed inside its own period is current. Refetching it would be traffic
     *  for nothing, and the network flaps more than the seed expires. */
    @Test
    fun `a current seed is left alone`() = runTest(dispatcher) {
        store.stored = seed(expiresAt = 1_000)

        running(keeper(now = 999)) {
            online.value = true
            runCurrent()
            online.value = false
            online.value = true
            runCurrent()

            assertEquals(0, repository.calls)
        }
    }

    @Test
    fun `nothing is fetched while signed out`() = runTest(dispatcher) {
        signedIn.value = false
        store.stored = null

        running(keeper()) {
            online.value = true
            runCurrent()

            assertEquals(0, repository.calls)
            assertNull(store.stored)
        }
    }

    /** A failed fetch leaves what was there. The screen reports properly when
     *  somebody opens it; this one is not allowed to make things worse. */
    @Test
    fun `a failing fetch keeps the old seed`() = runTest(dispatcher) {
        val old = seed(expiresAt = 0)
        store.stored = old
        repository.result = ApiResult.Failure(ApiError.Network(IOException("offline")))

        running(keeper(now = 10)) {
            online.value = true
            runCurrent()

            assertEquals(old, store.stored)
        }
    }

    /**
     * The periodic job is registered from the foreground, because nothing else
     * in the app ever runs otherwise: a job that only scheduled itself would
     * never come into existence.
     */
    @Test
    fun `opening the app registers the periodic refresh`() = runTest(dispatcher) {
        running(keeper()) {
            assertEquals(1, scheduled)
        }
    }

    /**
     * The wake-up path, which is the one that works with the app closed. It
     * shares the keeper's rule rather than repeating it — an observer with its
     * own idea of "expired" would be a second answer to the same question.
     */
    @Test
    fun `a push wake-up tops the seed up`() = runTest(dispatcher) {
        store.stored = seed(expiresAt = 0)

        SeedWakeupObserver(keeper(now = 10)).afterDrain()

        assertEquals(FETCHED, store.stored)
    }

    @Test
    fun `a push wake-up leaves a current seed alone`() = runTest(dispatcher) {
        store.stored = seed(expiresAt = 1_000)

        SeedWakeupObserver(keeper(now = 999)).afterDrain()

        assertEquals(0, repository.calls)
    }

    private fun seed(expiresAt: Long) = AttendanceSeed(
        memberRef = "MNOPQRSTUVWX2345",
        seed = "STORED",
        tenantId = "tenant-1",
        expiresAtEpochSeconds = expiresAt,
    )

    private companion object {
        val FETCHED = AttendanceSeed(
            memberRef = "MNOPQRSTUVWX2345",
            seed = "FETCHED",
            tenantId = "tenant-1",
            expiresAtEpochSeconds = Long.MAX_VALUE,
        )
    }

    private class KeeperSeedStore : SeedStore {
        var stored: AttendanceSeed? = null

        override val cached: AttendanceSeed? get() = stored

        override suspend fun read() = stored

        override suspend fun write(seed: AttendanceSeed) {
            stored = seed
        }

        override suspend fun clear() {
            stored = null
        }
    }

    private class KeeperRepository : AttendanceRepository {
        var calls = 0
        var result: ApiResult<AttendanceSeed> = ApiResult.Success(FETCHED)

        override suspend fun seed(): ApiResult<AttendanceSeed> {
            calls++
            return result
        }

        override suspend fun openSessions() = error("not used")

        override suspend fun scan(
            sessionId: String,
            code: String,
            installId: String?,
            staffDeviceId: String?,
            checkedInAt: String?,
        ) = error("not used")

        override suspend fun checkInManually(
            sessionId: String,
            memberId: String?,
            guestName: String?,
            checkedInAt: String?,
            clientId: String?,
        ) = error("not used")

        override suspend fun createSession(title: String, opensAt: String, closesAt: String) =
            error("not used")

        override suspend fun members(search: String?) = error("not used")

        override suspend fun sessionRecords(sessionId: String) = error("not used")

        override suspend fun latestOwnCheckIn() = error("not used")

        override suspend fun deleteRecord(recordId: String, reason: String?) = error("not used")

        override suspend fun myRangeDays() = error("not used")

        override suspend fun createSelfEntry(occurredOn: String, location: String) =
            error("not used")

        override suspend fun deleteSelfEntry(recordId: String) = error("not used")

        override suspend fun todaysEvents(startIso: String, endIso: String) = error("not used")

        override suspend fun openSessionForEvent(eventId: String) = error("not used")
    }
}
