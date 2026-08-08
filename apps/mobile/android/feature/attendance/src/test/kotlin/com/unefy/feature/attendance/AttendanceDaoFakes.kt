package com.unefy.feature.attendance

import com.unefy.core.database.CachedSession
import com.unefy.core.database.CachedSessionDao
import com.unefy.core.database.CachedSessionRecord
import com.unefy.core.database.CachedSessionRecordDao
import com.unefy.core.database.SyncCursorDao
import com.unefy.core.database.SyncCursorEntity
import com.unefy.core.database.SyncedMember
import com.unefy.core.database.SyncedMemberDao
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf

/**
 * The Room side of the attendance repository, in memory.
 *
 * Shared rather than repeated per test file: the repository takes five DAOs and
 * most tests care about one of them, so every new test would otherwise start by
 * writing four empty implementations.
 */
class FakeSyncedMemberDao : SyncedMemberDao {
    var rows: List<SyncedMember> = emptyList()
    var lastQuery: String? = null

    override fun search(query: String): Flow<List<SyncedMember>> {
        lastQuery = query
        return flowOf(rows)
    }

    override fun searchFolded(query: String): Flow<List<SyncedMember>> = flowOf(rows)

    override fun countStream(): Flow<Int> = flowOf(rows.size)

    override fun byIdStream(id: String): Flow<SyncedMember?> = flowOf(rows.find { it.id == id })

    override suspend fun upsert(members: List<SyncedMember>) = Unit

    override suspend fun deleteByIdsOf(ids: List<String>) = Unit

    override suspend fun sweep(generation: Long) = Unit

    override suspend fun deleteAll() = Unit
}

class FakeSyncCursorDao : SyncCursorDao {
    var bootstrapComplete = false

    override suspend fun get(collection: String): SyncCursorEntity? = null

    override fun bootstrapCompleteStream(collection: String): Flow<Boolean> =
        flowOf(bootstrapComplete)

    override suspend fun upsert(cursor: SyncCursorEntity) = Unit

    override suspend fun deleteAll() = Unit
}

class FakeCachedSessionDao : CachedSessionDao {
    /** What the cache holds. Written by upsert, so a test can see what landed. */
    var rows: List<CachedSession> = emptyList()

    override suspend fun upsert(sessions: List<CachedSession>) {
        val incoming = sessions.associateBy(CachedSession::id)
        rows = rows.filterNot { it.id in incoming } + sessions
    }

    override suspend fun all(): List<CachedSession> = rows

    override suspend fun retainOnlyOf(keep: List<String>) {
        rows = rows.filter { it.id in keep }
    }

    override suspend fun deleteAll() {
        rows = emptyList()
    }
}

class FakeCachedSessionRecordDao : CachedSessionRecordDao {
    override suspend fun upsert(records: List<CachedSessionRecord>) = Unit

    override suspend fun forSession(sessionId: String): List<CachedSessionRecord> = emptyList()

    override suspend fun retainOnlyOf(sessionId: String, keep: List<String>) = Unit

    override suspend fun deleteForSession(sessionId: String) = Unit

    override suspend fun deleteAll() = Unit
}
