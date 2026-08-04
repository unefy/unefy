package com.unefy.core.testing

import com.unefy.core.sync.ChangeHint
import com.unefy.core.sync.SyncCoordinator
import com.unefy.core.sync.SyncStatus
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.filter

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

    /**
     * Ring the doorbell from a test. Unfiltered on purpose — [signals] does the
     * filtering, so a test that emits the wrong entity should see nothing happen.
     */
    val hints = MutableSharedFlow<ChangeHint>(extraBufferCapacity = 16)

    override fun status(collection: String): Flow<SyncStatus> = status

    override fun signals(entity: String): Flow<ChangeHint> = hints.filter { it.entity == entity }

    override suspend fun request(collection: String) {
        requested += collection
    }

    override suspend fun requestAll() {
        requested += "*"
    }

    override suspend fun syncNow(collection: String) {
        syncedNow += collection
        if (blockSync) awaitCancellation()
    }

    override suspend fun run(): Nothing = awaitCancellation()

    override fun forgetStatuses() = Unit
}
