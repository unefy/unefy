package com.unefy.core.testing

import com.unefy.core.sync.SyncCoordinator
import com.unefy.core.sync.SyncStatus
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow

/**
 * A [SyncCoordinator] for ViewModel tests: status is a knob, syncs are a log.
 *
 * One shared fake rather than one per feature module — four screens follow the
 * same mirror pattern, and four private copies of this class would drift the
 * moment the interface gains a method.
 */
class FakeCoordinator(
    initial: SyncStatus = SyncStatus.Idle,
    private val blockSync: Boolean = false,
) : SyncCoordinator {

    val status = MutableStateFlow(initial)
    val syncedNow = mutableListOf<String>()
    val requested = mutableListOf<String>()

    override fun status(collection: String): Flow<SyncStatus> = status

    override suspend fun request(collection: String) {
        requested += collection
    }

    override suspend fun syncNow(collection: String) {
        syncedNow += collection
        if (blockSync) awaitCancellation()
    }

    override suspend fun run(): Nothing = awaitCancellation()

    override fun forgetStatuses() = Unit
}
