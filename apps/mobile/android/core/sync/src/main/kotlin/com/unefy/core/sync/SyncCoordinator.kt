package com.unefy.core.sync

import com.unefy.core.network.ApiError
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** What a screen can say about its collection's freshness. */
sealed interface SyncStatus {
    data object Idle : SyncStatus
    data object Syncing : SyncStatus

    /**
     * The last attempt failed. The mirror is still whatever it was, which for a
     * dropped connection is usually a minute out of date — worth a banner, never
     * worth replacing the list with an error.
     */
    data class Failed(val error: ApiError) : SyncStatus

    /** This account's role may not mirror the collection. Nothing to retry. */
    data object NotPermitted : SyncStatus
}

/**
 * The sync machinery as its callers see it.
 *
 * An interface because its callers are three different kinds of thing — a screen
 * that wants freshness and a refresh gesture, the activity that owns the
 * lifecycle, and sign-out — and because a ViewModel test should be able to say
 * "syncing failed" without standing up a stream, a connectivity monitor and an
 * HTTP client to make it happen.
 */
interface SyncCoordinator {

    /** What a screen can say about one collection's freshness. */
    fun status(collection: String): Flow<SyncStatus>

    /**
     * Asks for a drain of one collection, to happen shortly. Returns immediately.
     *
     * For hints and connectivity, where the point is that many reasons collapse
     * into one sync. A user gesture wants [syncNow] instead.
     */
    suspend fun request(collection: String)

    /**
     * Drains one collection and waits for it.
     *
     * For pull-to-refresh, which needs to know when it is done in order to stop
     * spinning — and which skips the coalescing window because somebody is
     * watching.
     */
    suspend fun syncNow(collection: String)

    /** Runs until cancelled. See [DefaultSyncCoordinator] for where to launch it. */
    suspend fun run()

    /**
     * Forgets every latched verdict, so the next sign-in starts from scratch.
     *
     * Public only because sign-out lives beside this rather than inside it; nothing
     * on a screen has any business calling it.
     */
    fun forgetStatuses()
}

/**
 * Decides when to sync, and makes sure a burst of reasons produces one sync.
 *
 * Three things ask for a sync and they arrive on very different schedules: the app
 * coming to the foreground (once), the network returning (rarely), and change
 * hints from the stream (in bursts — one save in the web app that touches five
 * rows is five hints). The bursts are why requests are collected for a moment
 * before being served: five hints about the same collection are one delta to
 * fetch, and fetching it five times would be the same answer four extra times.
 *
 * Lifecycle is the caller's business. [run] is meant to be launched from
 * `repeatOnLifecycle(STARTED)` in the single activity, so the stream is open
 * exactly while somebody is looking at the app. Android kills long-lived sockets
 * in the background anyway; closing it deliberately is honest rather than
 * pretending otherwise. Background freshness is a push problem, and push is FCM
 * (phase 5).
 */
@Singleton
class DefaultSyncCoordinator @Inject constructor(
    private val collections: Set<@JvmSuppressWildcards SyncCollection>,
    private val engine: SyncEngine,
    private val changeStream: ChangeStream,
    private val connectivity: ConnectivityMonitor,
) : SyncCoordinator {

    private val statuses = MutableStateFlow<Map<String, SyncStatus>>(emptyMap())

    private val byName: Map<String, SyncCollection> = collections.associateBy(SyncCollection::name)

    private val pending = mutableSetOf<String>()

    /**
     * Collections whose pending drain came from a change hint, and therefore needs
     * a second drain once the server will admit the change. See [SETTLE_DELAY_MS].
     */
    private val settling = mutableSetOf<String>()

    private val lock = Mutex()

    /**
     * Conflated on purpose. It signals "there is something in [pending]", and two
     * such signals mean the same thing as one — the set is where the detail lives.
     */
    private val wakeup = Channel<Unit>(Channel.CONFLATED)

    override fun status(collection: String): Flow<SyncStatus> = statuses
        .map { it[collection] ?: SyncStatus.Idle }
        .distinctUntilChanged()

    /**
     * Asks for a drain of one collection, to happen shortly. Returns immediately.
     *
     * For hints and connectivity, where the point is that many reasons collapse
     * into one sync. A user gesture wants [syncNow] instead.
     */
    override suspend fun request(collection: String) = request(listOf(collection))

    /**
     * Drains one collection and waits for it.
     *
     * For pull-to-refresh, which needs to know when it is done in order to stop
     * spinning — and which skips the coalescing window because somebody is
     * watching. Returns without doing anything if the collection is not mirrored
     * or has been refused.
     */
    override suspend fun syncNow(collection: String) {
        val target = byName[collection] ?: return
        if (statuses.value[collection] == SyncStatus.NotPermitted) return
        syncOne(target)
    }

    /** Runs until cancelled. See the class docstring for where to launch it. */
    override suspend fun run(): Unit = coroutineScope {
        launch { serveRequests(this@coroutineScope) }

        launch {
            // A drain on every transition to online, including the first — that
            // first one is what fills the mirror on a fresh install.
            connectivity.isOnline().filter { it }.collect { requestAll() }
        }

        launch {
            // The stream lives under the same scope, so it closes when the app
            // stops. Its own failures are Ktor's to retry; if it gives up
            // entirely, the app is still correct — just no longer instant.
            runCatching {
                changeStream.hints().collect { hint ->
                    request(listOf(hint.entity), settle = true)
                }
            }
        }
    }

    private suspend fun requestAll() = request(byName.keys)

    private suspend fun request(names: Collection<String>, settle: Boolean = false) {
        val wanted = names.filter { name ->
            // Unknown names are ordinary: the server streams hints for every
            // collection it knows, and this app mirrors one of them so far.
            //
            // NotPermitted is latched, which is also why `GET /sync/manifest` is
            // not called. The manifest would answer the same question one request
            // earlier; latching the 403 answers it once per session either way,
            // and without a second source of truth for what this role may read.
            // The one case the manifest would catch sooner — a role downgraded
            // while the app is open — needs more than a skipped sync anyway: the
            // mirror that account already holds would have to go, and that is a
            // decision for whenever roles become changeable from inside the app.
            byName.containsKey(name) && statuses.value[name] != SyncStatus.NotPermitted
        }
        if (wanted.isEmpty()) return

        lock.withLock {
            pending += wanted
            if (settle) settling += wanted
        }
        wakeup.trySend(Unit)
    }

    private suspend fun serveRequests(scope: CoroutineScope) {
        for (signal in wakeup) {
            // The coalescing window. Long enough that a save touching several rows
            // arrives as one batch, short enough that nobody watching the screen
            // reads it as lag.
            delay(COALESCE_WINDOW_MS)

            val batch: List<String>
            val settle: Set<String>
            lock.withLock {
                batch = pending.toList()
                settle = settling.intersect(pending)
                pending.clear()
                settling.clear()
            }

            for (name in batch) {
                byName[name]?.let { syncOne(it) }
            }

            // The drain above was almost certainly too early, and this is the fix
            // for it. See [SETTLE_DELAY_MS].
            if (settle.isNotEmpty()) {
                scope.launch {
                    delay(SETTLE_DELAY_MS)
                    request(settle)
                }
            }
        }
    }

    /**
     * One drain at a time.
     *
     * Two drains of the same collection would interleave their cursor writes, and
     * the one that finished second would store a position the other had already
     * passed — re-reading a page in the best case and, if their pages differed,
     * storing a cursor for rows that were never applied. Easy to provoke: pull to
     * refresh while a hint from the stream is being served.
     *
     * A single lock rather than one per collection. Drains are already sequential
     * in [serveRequests], so per-collection locks would buy concurrency that
     * nothing asks for, at the price of a lock map to reason about.
     */
    private val draining = Mutex()

    private suspend fun syncOne(collection: SyncCollection) = draining.withLock {
        setStatus(collection.name, SyncStatus.Syncing)
        val outcome = engine.sync(collection)
        setStatus(
            collection.name,
            when (outcome) {
                SyncOutcome.UpToDate -> SyncStatus.Idle
                SyncOutcome.NotPermitted -> SyncStatus.NotPermitted
                is SyncOutcome.Failed -> SyncStatus.Failed(outcome.error)
            },
        )
    }

    private fun setStatus(collection: String, status: SyncStatus) {
        statuses.value = statuses.value + (collection to status)
    }

    /**
     * Forgets every latched verdict, so the next sign-in starts from scratch.
     *
     * Without this a board member signing in after a plain member would inherit
     * the plain member's [SyncStatus.NotPermitted] and never sync anything —
     * a singleton outliving the account it learned from.
     */
    override fun forgetStatuses() {
        statuses.value = emptyMap()
    }

    private companion object {
        const val COALESCE_WINDOW_MS = 250L
    }
}

/**
 * How long after a hint the change actually becomes readable.
 *
 * The hint is published after commit, but the sync query deliberately
 * refuses to read anything newer than `now() - CURSOR_SAFETY_LAG`
 * (5 seconds, see backend/app/sync/cursor.py). `updated_at` is transaction
 * *start* time, so without that watermark a slow transaction could commit
 * behind a cursor already handed out and never be delivered at all.
 *
 * The consequence for this side is the whole reason this constant exists,
 * and it is not obvious: a drain served a quarter-second after the doorbell
 * asks for changes the server is still holding back. It returns nothing,
 * stores the cursor, and reports success — and since nothing else ever asks
 * again, the change stays invisible until some unrelated edit happens to
 * trigger the next sync. Verified on a device: a member renamed in the web
 * app did not appear at all, not even late.
 *
 * So a hint schedules two drains: one now, which usually finds nothing and
 * costs one small request, and one after the watermark has moved past the
 * change. The second is the one that actually delivers.
 *
 * Comfortably past the server's five seconds rather than exactly on it —
 * the two clocks are unrelated, and being early here means missing the
 * change entirely rather than merely waiting for it.
 *
 * Top-level rather than private to the coordinator: the FCM wake-up worker
 * waits the same lag for the same reason, and two copies of this number would
 * drift the day the server's lag changes.
 */
const val SETTLE_DELAY_MS = 6_500L
