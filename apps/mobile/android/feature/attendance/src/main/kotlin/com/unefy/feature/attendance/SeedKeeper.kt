package com.unefy.feature.attendance

import android.content.Context
import com.unefy.core.auth.AuthRepository
import com.unefy.core.network.ApiResult
import com.unefy.core.sync.ConnectivityMonitor
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.first

/**
 * Whether an account is signed in on this device.
 *
 * A seam of its own for the same reason [ConnectivityMonitor] is one: the real
 * `AuthRepository` reaches into an encrypted DataStore and a Keystore key, and
 * the rule worth proving here — a signed-out device makes no requests — needs
 * neither.
 */
fun interface SignedInSource {
    fun isSignedIn(): Flow<Boolean>
}

/**
 * Registers the periodic refresh. An interface for the same reason
 * [SyncScheduler] is one: scheduling is a side effect on the platform, and the
 * keeper's rules are worth testing without WorkManager.
 */
fun interface SeedRefreshScheduler {
    fun schedule()
}

/**
 * Keeps a usable check-in seed on the device while there is any signal to get
 * one with.
 *
 * The gap it closes: the seed used to be fetched in one place only — when the
 * check-in screen was opened. A member who used the app all week without ever
 * opening that tab arrived at the range with a seed from the last time they
 * did, and a seed stops verifying two periods after its own (see
 * [AttendanceCode.seedRejectedFrom]). The screen would then show a code that
 * cannot work, in the one place with no connection to fix it.
 *
 * So the fetch is moved to where the connection is rather than where the screen
 * is. Cheap: one request, and only when the stored seed has actually run out.
 *
 * Not a sync collection. There is nothing to mirror and nothing to merge — one
 * value, replaced wholesale, useless to anybody but its owner.
 */
@Singleton
class SeedKeeper @Inject constructor(
    private val repository: AttendanceRepository,
    private val seedStore: SeedStore,
    private val clock: AttendanceClock,
    private val connectivity: ConnectivityMonitor,
    private val auth: SignedInSource,
    private val scheduler: SeedRefreshScheduler,
) {

    /**
     * Runs for as long as the caller keeps it alive — MainActivity scopes it to
     * STARTED, like the sync loop and the push registration.
     */
    suspend fun run() {
        // Every foreground start re-registers the periodic job, which is unique
        // and KEEP, so this costs nothing after the first. It has to happen from
        // somewhere the app actually reaches: a job that only ever schedules
        // itself would never exist in the first place.
        scheduler.schedule()

        connectivity.isOnline()
            .distinctUntilChanged()
            .collect { online -> if (online) refreshIfExpired() }
    }

    /**
     * Fetches a seed if the stored one has run out, and does nothing otherwise.
     *
     * Public because three callers share this one rule: the foreground keeper
     * above, the periodic worker, and the wake-up observer that rides along on a
     * push. Putting the rule anywhere else would mean three chances to get
     * "when is a refetch warranted" subtly different.
     *
     * Not "when it is about to expire": the server keeps accepting a seed for
     * two more periods, so a phone with any connection at all has days of slack,
     * and refetching a working seed would be a request per network change for
     * nothing.
     */
    suspend fun refreshIfExpired() {
        // Checked here rather than at each caller: a signed-out device makes no
        // requests, and the worker runs whether or not anybody is signed in.
        if (!auth.isSignedIn().first()) return

        val stored = seedStore.read()
        if (stored != null && clock.epochSeconds() < stored.expiresAtEpochSeconds) return

        // Silent either way. Nobody asked for this and nothing is on screen: a
        // 404 means the account has no member record, and a failure means the
        // connection went again — the check-in screen says both properly when
        // somebody actually opens it.
        val result = repository.seed()
        if (result is ApiResult.Success) seedStore.write(result.data)
    }
}

@Module
@InstallIn(SingletonComponent::class)
object SeedKeeperModule {

    @Provides
    @Singleton
    fun provideSignedInSource(auth: AuthRepository): SignedInSource =
        SignedInSource { auth.isSignedIn }

    @Provides
    @Singleton
    fun provideSeedRefreshScheduler(@ApplicationContext context: Context): SeedRefreshScheduler =
        SeedRefreshScheduler { SeedRefreshWorker.schedule(context) }
}
