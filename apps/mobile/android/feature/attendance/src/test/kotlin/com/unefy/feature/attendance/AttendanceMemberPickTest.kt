package com.unefy.feature.attendance

import com.unefy.core.database.CachedSession
import com.unefy.core.database.CachedSessionDao
import com.unefy.core.database.CachedSessionRecord
import com.unefy.core.database.CachedSessionRecordDao
import com.unefy.core.database.SyncCursorDao
import com.unefy.core.database.SyncCursorEntity
import com.unefy.core.database.SyncedMember
import com.unefy.core.database.SyncedMemberDao
import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiResult
import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.respond
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.http.ContentType
import io.ktor.http.HttpStatusCode
import io.ktor.http.headersOf
import io.ktor.serialization.kotlinx.json.json
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Where the manual check-in pick list gets its names from.
 *
 * The rule under test: once the member mirror has bootstrapped, the list is
 * answered locally — the basement the old `cached_members` cache was built for
 * needs no network at all. The network path exists only for the window between
 * a fresh sign-in and the end of the bootstrap.
 */
class AttendanceMemberPickTest {

    private val members = FakeSyncedMemberDao()
    private val cursors = FakeSyncCursorDao()
    private var requests = 0

    private fun repository(networkBody: String = "[]"): DefaultAttendanceRepository {
        val engine = MockEngine {
            requests++
            respond(
                content = """{"data": $networkBody}""",
                status = HttpStatusCode.OK,
                headers = headersOf("Content-Type", ContentType.Application.Json.toString()),
            )
        }
        val httpClient = HttpClient(engine) {
            install(ContentNegotiation) { json(Json) }
        }
        return DefaultAttendanceRepository(
            apiClient = ApiClient(httpClient),
            syncedMembers = members,
            syncCursors = cursors,
            sessionCache = FakeCachedSessionDao(),
            recordCache = FakeCachedSessionRecordDao(),
        )
    }

    @Test
    fun `a bootstrapped mirror answers the pick list without the network`() = runTest {
        cursors.bootstrapComplete = true
        members.rows = listOf(row("m1", "100", "Anna", "Müller"), row("m2", "101", "Ben", "Ott"))

        val result = repository().members(search = null)

        assertEquals(
            listOf(MemberPick("m1", "100", "Anna Müller"), MemberPick("m2", "101", "Ben Ott")),
            (result as ApiResult.Success).data,
        )
        assertEquals(0, requests)
    }

    @Test
    fun `the search is delegated to the mirror's folded search`() = runTest {
        cursors.bootstrapComplete = true

        repository().members(search = "Mü")

        assertEquals("Mü", members.lastQuery)
        assertEquals(0, requests)
    }

    @Test
    fun `before the bootstrap the list still comes from the network`() = runTest {
        cursors.bootstrapComplete = false

        val result = repository(
            """[{"id": "m9", "member_number": "900", "first_name": "Cem", "last_name": "Yilmaz"}]""",
        ).members(search = null)

        assertEquals(
            listOf(MemberPick("m9", "900", "Cem Yilmaz")),
            (result as ApiResult.Success).data,
        )
        assertEquals(1, requests)
    }
}

private fun row(id: String, number: String, first: String, last: String) = SyncedMember(
    id = id,
    memberNumber = number,
    firstName = first,
    lastName = last,
    email = null,
    phone = null,
    mobile = null,
    birthday = null,
    street = null,
    zipCode = null,
    city = null,
    status = null,
    category = null,
    joinedAt = "2020-01-01",
    leftAt = null,
    generation = 1,
)

private class FakeSyncedMemberDao : SyncedMemberDao {
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

private class FakeSyncCursorDao : SyncCursorDao {
    var bootstrapComplete = false

    override suspend fun get(collection: String): SyncCursorEntity? = null

    override fun bootstrapCompleteStream(collection: String): Flow<Boolean> =
        flowOf(bootstrapComplete)

    override suspend fun upsert(cursor: SyncCursorEntity) = Unit

    override suspend fun deleteAll() = Unit
}

private class FakeCachedSessionDao : CachedSessionDao {
    override suspend fun upsert(sessions: List<CachedSession>) = Unit

    override suspend fun all(): List<CachedSession> = emptyList()

    override suspend fun retainOnlyOf(keep: List<String>) = Unit

    override suspend fun deleteAll() = Unit
}

private class FakeCachedSessionRecordDao : CachedSessionRecordDao {
    override suspend fun upsert(records: List<CachedSessionRecord>) = Unit

    override suspend fun forSession(sessionId: String): List<CachedSessionRecord> = emptyList()

    override suspend fun retainOnlyOf(sessionId: String, keep: List<String>) = Unit

    override suspend fun deleteForSession(sessionId: String) = Unit

    override suspend fun deleteAll() = Unit
}
