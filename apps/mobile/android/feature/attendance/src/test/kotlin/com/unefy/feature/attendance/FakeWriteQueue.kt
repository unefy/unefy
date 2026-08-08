package com.unefy.feature.attendance

import com.unefy.core.database.PendingWrite
import com.unefy.core.sync.WriteQueue
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.map

/**
 * The write queue, in memory.
 *
 * Records what was queued and in which order it was drained, because both are
 * what the attendance side has to get right: an evening opened at the range is
 * a queued write, and its check-ins may not leave before it does.
 */
class FakeWriteQueue : WriteQueue {

    private val rows = MutableStateFlow<List<PendingWrite>>(emptyList())

    /** Appended by [drain] and by the check-in queue's sends, in call order. */
    val calls = mutableListOf<String>()

    val queued: List<PendingWrite> get() = rows.value

    override suspend fun enqueue(
        entity: String,
        recordId: String,
        op: String,
        payloadJson: String,
        label: String,
    ) {
        rows.value = rows.value.filterNot { it.entity == entity && it.recordId == recordId } +
            PendingWrite(
                entity = entity,
                recordId = recordId,
                op = op,
                tenantId = "tenant-1",
                payloadJson = payloadJson,
                label = label,
                queuedAt = "2026-08-08T18:00:00Z",
            )
    }

    override fun pending(entity: String): Flow<List<PendingWrite>> =
        rows.map { all -> all.filter { it.entity == entity } }

    override fun pendingFor(entity: String, recordId: String): Flow<PendingWrite?> =
        rows.map { all -> all.firstOrNull { it.entity == entity && it.recordId == recordId } }

    override fun count(): Flow<Int> = rows.map { it.size }

    override suspend fun drain(): Int {
        calls += "drain-writes"
        val sent = rows.value.size
        rows.value = emptyList()
        return sent
    }

    override suspend fun discard(entity: String, recordId: String) {
        rows.value = rows.value.filterNot { it.entity == entity && it.recordId == recordId }
    }
}
