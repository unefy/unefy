package com.unefy.feature.scoring

import com.unefy.core.database.CachedShotEntry
import com.unefy.core.database.CachedShotEntryDao
import com.unefy.core.database.PendingShotEntry
import com.unefy.core.database.PendingShotEntryDao
import com.unefy.core.database.SyncedEntry
import com.unefy.core.database.SyncedEntryDao
import com.unefy.core.database.SyncedMember
import com.unefy.core.database.SyncedMemberDao
import com.unefy.core.model.scoring.PlacedShot
import com.unefy.core.model.scoring.ShotSeriesDraft
import com.unefy.core.model.scoring.TargetGeometrySeed
import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiResult
import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.respond
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.http.headersOf
import io.ktor.serialization.kotlinx.json.json
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * That correcting and withdrawing a series reach the *club* mirror, not only the
 * caller's own cache.
 *
 * Why it matters: the club list and its detail screen read `synced_entries`,
 * which is otherwise only ever written by delta-sync. Leaving it alone meant a
 * board member corrected a series and went on looking at the old rings until the
 * next sync — indistinguishable from a save that failed.
 */
class ScoringRepositoryMirrorTest {

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    @Test
    fun `a correction is written into the club mirror`() = runTest {
        val mirror = FakeSyncedEntryDao(listOf(mirrorRow(total = 39.0, generation = 7)))
        val repository = repository(mirror, respondWith = entryJson(total = 20.0))

        val result = repository.correct(SERIES_ID, draft())

        assertEquals(ApiResult.Success(Unit), result)
        val row = mirror.rows.value.single()
        assertEquals("the server's total, not the client's", 20.0, row.scoreValue, 0.0)
        // Carried over, not invented: a lower generation would be swept away by
        // the next bootstrap, a higher one would survive a sweep it should not.
        assertEquals(7L, row.generation)
    }

    @Test
    fun `a correction of a series that is not mirrored leaves the mirror alone`() = runTest {
        // A plain member's device never receives the collection. Inventing a row
        // here would show them club data they are not entitled to.
        val mirror = FakeSyncedEntryDao(emptyList())
        val repository = repository(mirror, respondWith = entryJson(total = 20.0))

        repository.correct(SERIES_ID, draft())

        assertEquals(emptyList<SyncedEntry>(), mirror.rows.value)
    }

    @Test
    fun `withdrawing a series removes it from the club mirror`() = runTest {
        val mirror = FakeSyncedEntryDao(listOf(mirrorRow(total = 39.0, generation = 7)))
        val repository = repository(mirror, respondWith = "", status = HttpStatusCode.NoContent)

        val result = repository.delete(SERIES_ID)

        assertEquals(ApiResult.Success(Unit), result)
        assertNull(mirror.rows.value.firstOrNull { it.id == SERIES_ID })
    }

    @Test
    fun `a failed correction leaves the mirror untouched`() = runTest {
        val mirror = FakeSyncedEntryDao(listOf(mirrorRow(total = 39.0, generation = 7)))
        val repository = repository(
            mirror,
            respondWith = """{"error":{"code":"FORBIDDEN","message":"nope"}}""",
            status = HttpStatusCode.Forbidden,
        )

        repository.correct(SERIES_ID, draft())

        assertEquals(39.0, mirror.rows.value.single().scoreValue, 0.0)
    }

    // --- Fixtures ---

    private fun repository(
        mirror: SyncedEntryDao,
        respondWith: String,
        status: HttpStatusCode = HttpStatusCode.OK,
    ): ScoringRepository {
        val engine = MockEngine {
            respond(
                content = respondWith,
                status = status,
                headers = headersOf(HttpHeaders.ContentType, ContentType.Application.Json.toString()),
            )
        }
        val client = HttpClient(engine) { install(ContentNegotiation) { json(json) } }
        return DefaultScoringRepository(
            apiClient = ApiClient(client),
            pendingDao = EmptyPendingDao,
            cacheDao = NoopCacheDao,
            syncedEntryDao = mirror,
            memberDao = EmptyMemberDao,
        )
    }

    private fun draft() = ShotSeriesDraft(
        geometry = TargetGeometrySeed.PRECISION_25M,
        caliberMm = 9.0,
        shots = listOf(PlacedShot("a", 0.0, 0.0, 10)),
    )

    private fun mirrorRow(total: Double, generation: Long) = SyncedEntry(
        id = SERIES_ID,
        sessionId = "sess-1",
        memberId = "m3",
        scoreValue = total,
        scoreUnit = "rings",
        discipline = null,
        targetType = TargetGeometrySeed.PRECISION_25M.slug,
        caliberMm = 9.0,
        shotsJson = null,
        innerTens = 1,
        groupingMm = 303.0,
        source = "manual",
        recordedAt = "2026-08-07T13:12:00Z",
        notes = null,
        generation = generation,
    )

    /** What the server answers a PATCH with — the rescored entry. */
    private fun entryJson(total: Double) = """
        {"data":{"id":"$SERIES_ID","session_id":"sess-1","member_id":"m3",
        "score_value":$total,"score_unit":"rings","source":"manual",
        "recorded_at":"2026-08-07T13:12:00Z",
        "created_at":"2026-08-07T13:12:00Z","updated_at":"2026-08-07T14:00:00Z"}}
    """.trimIndent().replace("\n", "")

    private companion object {
        const val SERIES_ID = "series-1"
    }
}

private class FakeSyncedEntryDao(initial: List<SyncedEntry>) : SyncedEntryDao {
    val rows = MutableStateFlow(initial)

    override fun all(): Flow<List<SyncedEntry>> = rows

    override fun byMember(memberId: String): Flow<List<SyncedEntry>> =
        rows.map { list -> list.filter { it.memberId == memberId } }

    override suspend fun byId(id: String): SyncedEntry? = rows.value.firstOrNull { it.id == id }

    override suspend fun upsert(entries: List<SyncedEntry>) {
        val ids = entries.mapTo(mutableSetOf()) { it.id }
        rows.value = rows.value.filterNot { it.id in ids } + entries
    }

    override suspend fun deleteByIds(ids: List<String>) {
        rows.value = rows.value.filterNot { it.id in ids }
    }

    override suspend fun sweep(generation: Long) {
        rows.value = rows.value.filter { it.generation >= generation }
    }

    override suspend fun deleteAll() {
        rows.value = emptyList()
    }
}

private object EmptyPendingDao : PendingShotEntryDao {
    override suspend fun insert(entry: PendingShotEntry) = Unit
    override suspend fun update(entry: PendingShotEntry) = Unit
    override suspend fun all(): List<PendingShotEntry> = emptyList()
    override fun stream(): Flow<List<PendingShotEntry>> = MutableStateFlow(emptyList())
    override fun streamForMember(memberId: String): Flow<List<PendingShotEntry>> =
        MutableStateFlow(emptyList())
    override suspend fun byId(id: String): PendingShotEntry? = null
    override fun countStream(): Flow<Int> = MutableStateFlow(0)
    override suspend fun delete(id: String) = Unit
    override suspend fun recordFailure(id: String, error: String?) = Unit
    override suspend fun deleteAll() = Unit
}

private object NoopCacheDao : CachedShotEntryDao {
    override fun all(): Flow<List<CachedShotEntry>> = MutableStateFlow(emptyList())
    override fun byIdStream(id: String): Flow<CachedShotEntry?> = MutableStateFlow(null)
    override suspend fun upsert(entries: List<CachedShotEntry>) = Unit
    override suspend fun deleteById(id: String) = Unit
    override suspend fun deleteAll() = Unit
}

private object EmptyMemberDao : SyncedMemberDao {
    override fun searchFolded(query: String): Flow<List<SyncedMember>> = MutableStateFlow(emptyList())
    override fun countStream(): Flow<Int> = MutableStateFlow(0)
    override fun byIdStream(id: String): Flow<SyncedMember?> = MutableStateFlow(null)
    override suspend fun upsert(members: List<SyncedMember>) = Unit
    override suspend fun deleteByIdsOf(ids: List<String>) = Unit
    override suspend fun sweep(generation: Long) = Unit
    override suspend fun deleteAll() = Unit
}
