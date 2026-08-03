package com.unefy.core.push

import com.unefy.core.network.TokenStore
import com.unefy.core.sync.SyncCollection
import com.unefy.core.sync.SyncCoordinator
import javax.inject.Inject
import javax.inject.Singleton

/**
 * What a wake-up actually does, separated from WorkManager so a JVM test can
 * pin it: no session means no sync, a session means every registered
 * collection drains.
 *
 * All of them rather than the one the message named — wake-ups are coalesced
 * per club on the server, so the named entity is only the first of a possible
 * burst, and a drain of an unchanged collection costs one small request.
 */
@Singleton
class WakeupDrain @Inject constructor(
    private val coordinator: SyncCoordinator,
    private val collections: Set<@JvmSuppressWildcards SyncCollection>,
    private val tokens: TokenStore,
) {

    /** Returns false when skipped for lack of a session. */
    suspend fun drainAll(): Boolean {
        // A signed-out app has no business syncing — without a token every
        // drain is a 401 and a retry loop nobody asked for.
        if (tokens.current() == null) return false

        for (collection in collections) {
            // NotPermitted collections return immediately — latched in the
            // coordinator, same as on the foreground path.
            coordinator.syncNow(collection.name)
        }
        return true
    }
}
