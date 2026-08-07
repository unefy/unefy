package com.unefy.core.sync

import com.unefy.core.auth.TokenManager
import com.unefy.core.database.PendingWrite
import com.unefy.core.database.PendingWriteDao
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * The club whose name queued writes are filed under.
 *
 * An interface over `TokenManager.session` for the same reason
 * [ConnectivityMonitor] is one: the queue's rules — above all "never drain
 * another club's row" — are worth testing without standing up DataStore, a
 * Keystore key and an Android `Context` to do it.
 */
fun interface ActiveTenant {
    fun id(): Flow<String?>
}

@Singleton
class SessionActiveTenant @Inject constructor(
    private val tokens: TokenManager,
) : ActiveTenant {
    override fun id(): Flow<String?> = tokens.session.map { it?.tenant?.id }
}

/**
 * Sends one kind of queued write. Features implement it, the queue calls it.
 *
 * The same shape and the same reasoning as [SyncCollection]: the queue knows
 * about retrying, ordering and giving up, and nothing about what a member is.
 * Registered with Hilt `@IntoSet`.
 */
interface PendingWriteHandler {

    /** Matches [PendingWrite.entity] — `"members"`, `"events"`. */
    val entity: String

    /**
     * Send it. The queue deletes the row on success and keeps it on failure.
     *
     * Implementations do their own local bookkeeping here — writing the
     * server's answer into the mirror, typically — because only the feature
     * knows which table that is.
     */
    suspend fun send(write: PendingWrite): ApiResult<Unit>
}

/**
 * Creations and edits that have not reached the server yet.
 *
 * An interface so a ViewModel test can queue something without a database, and
 * because the drain policy is worth testing on its own.
 */
interface WriteQueue {

    /**
     * Put a write in the queue, replacing any unsent write for the same record.
     *
     * Returns nothing and cannot fail: that is the contract the form screens
     * rely on. Saving must not depend on a network, or the app is useless in
     * the clubhouse cellar where half of this data gets entered.
     */
    suspend fun enqueue(
        entity: String,
        recordId: String,
        op: String,
        payloadJson: String,
        label: String,
    )

    /** Unsent writes for one entity, oldest first. */
    fun pending(entity: String): Flow<List<PendingWrite>>

    /** One record's unsent write, if it has one. */
    fun pendingFor(entity: String, recordId: String): Flow<PendingWrite?>

    /** How many writes are waiting, for the current club only. */
    fun count(): Flow<Int>

    /** Try to send everything waiting. Returns how many made it. */
    suspend fun drain(): Int

    /** Throw one away — for a queued creation somebody decides against. */
    suspend fun discard(entity: String, recordId: String)
}

@OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
@Singleton
class DefaultWriteQueue @Inject constructor(
    private val dao: PendingWriteDao,
    private val handlers: Set<@JvmSuppressWildcards PendingWriteHandler>,
    private val activeTenant: ActiveTenant,
) : WriteQueue {

    private val byEntity: Map<String, PendingWriteHandler> =
        handlers.associateBy(PendingWriteHandler::entity)

    /**
     * One drain at a time. Two overlapping drains would send the same row
     * twice; the server tolerates that for creations, but only because the id
     * makes it idempotent, and an edit sent twice is a wasted round trip that
     * can still race its own answer.
     */
    private val drainLock = Mutex()

    override suspend fun enqueue(
        entity: String,
        recordId: String,
        op: String,
        payloadJson: String,
        label: String,
    ) {
        val tenantId = currentTenantId() ?: return
        val existing = dao.byId(entity, recordId)
        dao.upsert(
            PendingWrite(
                entity = entity,
                recordId = recordId,
                // A creation stays a creation. Editing a record the server has
                // never seen must not turn into a PATCH against an id that does
                // not exist there yet — the whole record still has to be sent.
                op = if (existing?.op == PendingWrite.OP_CREATE) PendingWrite.OP_CREATE else op,
                tenantId = tenantId,
                payloadJson = payloadJson,
                label = label,
                // An edit of something still queued keeps the original's place
                // in line. Re-stamping it would let a record edited twice
                // overtake one queued before it, and the queue's only ordering
                // promise is that things leave in the order they were made.
                queuedAt = existing?.queuedAt ?: nowIso(),
            ),
        )
    }

    override fun pending(entity: String): Flow<List<PendingWrite>> = dao.stream(entity)

    override fun pendingFor(entity: String, recordId: String): Flow<PendingWrite?> =
        dao.byIdStream(entity, recordId)

    override fun count(): Flow<Int> = activeTenant.id().flatMapLatest { tenantId ->
        if (tenantId == null) flowOf(0) else dao.countStream(tenantId)
    }

    override suspend fun drain(): Int = drainLock.withLock {
        val tenantId = currentTenantId() ?: return@withLock 0
        var sent = 0
        for (write in dao.drainable(tenantId)) {
            // Belt and braces, and deliberately so: the query already filters by
            // club, but this is the one rule whose failure creates a member in
            // somebody else's club, and a `WHERE` clause dropped in a future
            // refactor would do it silently. Checked here it is also checkable
            // by a test that does not need a device.
            if (write.tenantId != tenantId) continue

            val handler = byEntity[write.entity]
            if (handler == null) {
                // A queue row for a feature this build no longer has. Keeping
                // it would block everything queued behind it forever.
                dao.delete(write.entity, write.recordId)
                continue
            }

            when (val result = handler.send(write)) {
                is ApiResult.Success -> {
                    dao.delete(write.entity, write.recordId)
                    sent++
                }
                is ApiResult.Failure -> {
                    dao.recordFailure(write.entity, write.recordId, result.error.toString())
                    if (result.error is ApiError.Network) {
                        // No point walking the rest of the queue against a
                        // network that is plainly not there.
                        break
                    }
                    // Anything else is about *this* row — a validation error, a
                    // record deleted on the server meanwhile. Carry on, or one
                    // bad row would hold up everything behind it indefinitely.
                }
            }
        }
        sent
    }

    override suspend fun discard(entity: String, recordId: String) = dao.delete(entity, recordId)

    private suspend fun currentTenantId(): String? = activeTenant.id().first()

    private fun nowIso(): String = java.time.Instant.now().toString()
}
