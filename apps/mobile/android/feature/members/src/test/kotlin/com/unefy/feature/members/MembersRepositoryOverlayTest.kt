package com.unefy.feature.members

import com.unefy.core.database.PendingWrite
import com.unefy.core.database.SyncCursorDao
import com.unefy.core.database.SyncCursorEntity
import com.unefy.core.database.SyncedMember
import com.unefy.core.database.SyncedMemberDao
import com.unefy.core.network.ApiClient
import com.unefy.core.sync.WriteQueue
import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Unsent writes laid over the mirror.
 *
 * This is the seam where an edit can silently disappear. The queue holds the
 * change, the mirror does not know about it, and any screen reading the mirror
 * alone shows the old values — which to whoever just typed them is
 * indistinguishable from a save that failed. The list had the overlay from the
 * start; `byIdStream`, which the detail screen reads, did not, and that is what
 * these tests pin down.
 */
class MembersRepositoryOverlayTest {

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    @Test
    fun `an edited member shows the edit, not the mirror's older copy`() = runTest {
        val dao = FakeMemberDao(listOf(synced("m1", "Ida", "Beispiel")))
        val queue = FakeQueue()
        val repository = repository(dao, queue)

        repository.save("m1", MemberDraft(firstName = "Ida", lastName = "Neuname"))

        assertEquals("Neuname", repository.byIdStream("m1").first()?.lastName)
    }

    @Test
    fun `a member created on this device opens even though the mirror is empty`() = runTest {
        val dao = FakeMemberDao(emptyList())
        val queue = FakeQueue()
        val repository = repository(dao, queue)

        val id = repository.save(null, MemberDraft(firstName = "Neu", lastName = "Person"))

        val member = repository.byIdStream(id).first()
        assertEquals("Neu", member?.firstName)
        // No number yet — the server allocates it, and inventing one here would
        // put a number in the club's records that belongs to nobody.
        assertEquals("", member?.memberNumber)
    }

    @Test
    fun `a member that is neither mirrored nor queued is still null`() = runTest {
        val repository = repository(FakeMemberDao(emptyList()), FakeQueue())

        assertNull(repository.byIdStream("nobody").first())
    }

    @Test
    fun `the list shows the edit too`() = runTest {
        val dao = FakeMemberDao(listOf(synced("m1", "Ida", "Beispiel")))
        val repository = repository(dao, FakeQueue())

        repository.save("m1", MemberDraft(firstName = "Ida", lastName = "Neuname"))

        assertEquals("Neuname", repository.stream("").first().single().lastName)
    }

    /**
     * The two collaborators these tests exercise are the mirror and the queue.
     * The network and the cursor are wired to things that fail loudly if
     * touched — a stub that quietly answers would let a test pass because the
     * repository fell back to fetching, which is the opposite of what is
     * being checked.
     */
    private fun repository(dao: SyncedMemberDao, queue: WriteQueue) = DefaultMembersRepository(
        apiClient = ApiClient(
            HttpClient(MockEngine { error("this test must not reach the network") }),
        ),
        members = dao,
        cursors = RefusingCursorDao(),
        writes = queue,
        json = json,
    )

    private class RefusingCursorDao : SyncCursorDao {
        override suspend fun get(collection: String): SyncCursorEntity? = error("not used")
        override fun bootstrapCompleteStream(collection: String): Flow<Boolean> = error("not used")
        override suspend fun upsert(cursor: SyncCursorEntity) = error("not used")
        override suspend fun deleteAll() = error("not used")
    }

    private fun synced(id: String, first: String, last: String) = SyncedMember(
        id = id,
        memberNumber = "001",
        firstName = first,
        lastName = last,
        email = null,
        phone = null,
        mobile = null,
        birthday = null,
        gender = null,
        street = null,
        zipCode = null,
        city = null,
        status = "active",
        category = null,
        joinedAt = "2024-01-01",
        leftAt = null,
        generation = 1L,
    )

    /** Only the two reads the repository makes; the rest is never called. */
    private class FakeMemberDao(rows: List<SyncedMember>) : SyncedMemberDao {
        private val state = MutableStateFlow(rows)

        override fun searchFolded(query: String): Flow<List<SyncedMember>> = state.map { list ->
            if (query.isBlank()) list else list.filter { query in it.searchKey }
        }

        override fun byIdStream(id: String): Flow<SyncedMember?> =
            state.map { list -> list.firstOrNull { it.id == id } }

        override fun countStream(): Flow<Int> = state.map { it.size }
        override suspend fun upsert(members: List<SyncedMember>) = Unit
        override suspend fun deleteByIdsOf(ids: List<String>) = Unit
        override suspend fun sweep(generation: Long) = Unit
        override suspend fun deleteAll() = Unit
    }

    /** In-memory queue with the same replace-by-record rule the real one has. */
    private class FakeQueue : WriteQueue {
        private val rows = MutableStateFlow<List<PendingWrite>>(emptyList())

        override suspend fun enqueue(
            entity: String,
            recordId: String,
            op: String,
            payloadJson: String,
            label: String,
        ) {
            rows.value = rows.value.filterNot {
                it.entity == entity && it.recordId == recordId
            } + PendingWrite(
                entity = entity,
                recordId = recordId,
                op = op,
                tenantId = "club",
                payloadJson = payloadJson,
                label = label,
                queuedAt = "2026-08-08T10:00:00Z",
            )
        }

        override fun pending(entity: String): Flow<List<PendingWrite>> =
            rows.map { list -> list.filter { it.entity == entity } }

        override fun pendingFor(entity: String, recordId: String): Flow<PendingWrite?> =
            rows.map { list ->
                list.firstOrNull { it.entity == entity && it.recordId == recordId }
            }

        override fun count(): Flow<Int> = rows.map { it.size }
        override suspend fun drain(): Int = 0
        override suspend fun discard(entity: String, recordId: String) {
            rows.value = rows.value.filterNot {
                it.entity == entity && it.recordId == recordId
            }
        }
    }
}
