package com.unefy.core.sync

import com.unefy.core.database.PendingWrite
import com.unefy.core.database.PendingWriteDao
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import java.io.IOException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The queue's rules, which is where this feature can go quietly wrong.
 *
 * Everything here is about what happens when the network is not there — the
 * normal case in a clubhouse cellar, not the exception — and about the one
 * thing that must never happen: a write filed in the wrong club.
 */
class WriteQueueTest {

    // --- Fakes ---

    private class FakeDao : PendingWriteDao {
        val rows = MutableStateFlow<List<PendingWrite>>(emptyList())

        override suspend fun upsert(write: PendingWrite) {
            rows.value = rows.value.filterNot {
                it.entity == write.entity && it.recordId == write.recordId
            } + write
        }

        override fun stream(entity: String): Flow<List<PendingWrite>> =
            rows.map { list -> list.filter { it.entity == entity }.sortedBy { it.queuedAt } }

        override suspend fun byId(entity: String, recordId: String): PendingWrite? =
            rows.value.firstOrNull { it.entity == entity && it.recordId == recordId }

        override fun byIdStream(entity: String, recordId: String): Flow<PendingWrite?> =
            rows.map { list ->
                list.firstOrNull { it.entity == entity && it.recordId == recordId }
            }

        /** Filters like the real query does — unless [leaky] says otherwise. */
        var leaky = false

        override suspend fun drainable(tenantId: String): List<PendingWrite> =
            rows.value
                .filter { leaky || it.tenantId == tenantId }
                .sortedBy { it.queuedAt }

        override fun countStream(tenantId: String): Flow<Int> =
            rows.map { list -> list.count { it.tenantId == tenantId } }

        override suspend fun delete(entity: String, recordId: String) {
            rows.value = rows.value.filterNot {
                it.entity == entity && it.recordId == recordId
            }
        }

        override suspend fun recordFailure(entity: String, recordId: String, error: String?) {
            rows.value = rows.value.map {
                if (it.entity == entity && it.recordId == recordId) {
                    it.copy(attempts = it.attempts + 1, lastError = error)
                } else {
                    it
                }
            }
        }

        override suspend fun deleteAll() {
            rows.value = emptyList()
        }
    }

    private class FakeHandler(
        override val entity: String,
        var result: (PendingWrite) -> ApiResult<Unit> = { ApiResult.Success(Unit) },
    ) : PendingWriteHandler {
        val sent = mutableListOf<PendingWrite>()

        override suspend fun send(write: PendingWrite): ApiResult<Unit> {
            sent += write
            return result(write)
        }
    }

    private fun queue(
        dao: PendingWriteDao,
        handlers: Set<PendingWriteHandler>,
        tenantId: String? = TENANT,
    ) = DefaultWriteQueue(
        dao = dao,
        handlers = handlers,
        activeTenant = { MutableStateFlow(tenantId) },
    )

    // --- Enqueuing ---

    @Test
    fun `editing a queued record replaces its row instead of adding one`() = runTest {
        val dao = FakeDao()
        val handler = FakeHandler(MEMBERS)
        val q = queue(dao, setOf(handler))

        q.enqueue(MEMBERS, "m1", PendingWrite.OP_CREATE, """{"v":1}""", "Erst")
        q.enqueue(MEMBERS, "m1", PendingWrite.OP_CREATE, """{"v":2}""", "Dann")

        val pending = q.pending(MEMBERS).first()
        assertEquals(1, pending.size)
        assertEquals("""{"v":2}""", pending.single().payloadJson)
        assertEquals("Dann", pending.single().label)
    }

    @Test
    fun `editing a record the server has never seen stays a creation`() = runTest {
        val dao = FakeDao()
        val handler = FakeHandler(MEMBERS)
        val q = queue(dao, setOf(handler))

        q.enqueue(MEMBERS, "m1", PendingWrite.OP_CREATE, "{}", "Neu")
        // The form does not know the difference — it just saves an edit.
        q.enqueue(MEMBERS, "m1", PendingWrite.OP_UPDATE, """{"v":2}""", "Neu, korrigiert")

        // Sent as a creation, or the server gets a PATCH against an id it has
        // never heard of and answers 404 for a member that genuinely exists on
        // this phone.
        assertEquals(PendingWrite.OP_CREATE, q.pending(MEMBERS).first().single().op)
    }

    @Test
    fun `an edit keeps its place in line`() = runTest {
        val dao = FakeDao()
        val q = queue(dao, setOf(FakeHandler(MEMBERS)))

        q.enqueue(MEMBERS, "first", PendingWrite.OP_CREATE, "{}", "A")
        q.enqueue(MEMBERS, "second", PendingWrite.OP_CREATE, "{}", "B")
        q.enqueue(MEMBERS, "first", PendingWrite.OP_UPDATE, """{"v":2}""", "A2")

        // Re-stamping the edit would have let it overtake "second".
        assertEquals(listOf("first", "second"), q.pending(MEMBERS).first().map { it.recordId })
    }

    // --- Draining ---

    @Test
    fun `a successful send removes the row`() = runTest {
        val dao = FakeDao()
        val handler = FakeHandler(MEMBERS)
        val q = queue(dao, setOf(handler))
        q.enqueue(MEMBERS, "m1", PendingWrite.OP_CREATE, "{}", "Neu")

        assertEquals(1, q.drain())
        assertEquals(1, handler.sent.size)
        assertTrue(q.pending(MEMBERS).first().isEmpty())
    }

    @Test
    fun `a row is kept when the send fails, so nothing is lost`() = runTest {
        val dao = FakeDao()
        val handler = FakeHandler(MEMBERS) { ApiResult.Failure(ApiError.Network(IOException())) }
        val q = queue(dao, setOf(handler))
        q.enqueue(MEMBERS, "m1", PendingWrite.OP_CREATE, "{}", "Neu")

        assertEquals(0, q.drain())
        val kept = q.pending(MEMBERS).first().single()
        assertEquals(1, kept.attempts)
        assertTrue(kept.lastError != null)
    }

    @Test
    fun `a dead network stops the drain instead of hammering every row`() = runTest {
        val dao = FakeDao()
        val handler = FakeHandler(MEMBERS) { ApiResult.Failure(ApiError.Network(IOException())) }
        val q = queue(dao, setOf(handler))
        q.enqueue(MEMBERS, "m1", PendingWrite.OP_CREATE, "{}", "A")
        q.enqueue(MEMBERS, "m2", PendingWrite.OP_CREATE, "{}", "B")

        q.drain()

        assertEquals(1, handler.sent.size)
    }

    @Test
    fun `one rejected row does not block the ones behind it`() = runTest {
        val dao = FakeDao()
        // A record the server refuses on its own merits — a validation error,
        // or something deleted there meanwhile. Retrying cannot fix it, and
        // stopping would strand everything queued after it.
        val handler = FakeHandler(MEMBERS) { write ->
            if (write.recordId == "bad") {
                ApiResult.Failure(ApiError.Http(422, "VALIDATION_ERROR", "nope"))
            } else {
                ApiResult.Success(Unit)
            }
        }
        val q = queue(dao, setOf(handler))
        q.enqueue(MEMBERS, "bad", PendingWrite.OP_CREATE, "{}", "A")
        q.enqueue(MEMBERS, "good", PendingWrite.OP_CREATE, "{}", "B")

        assertEquals(1, q.drain())
        assertEquals(listOf("bad", "good"), handler.sent.map { it.recordId })
        // The bad one is still there, with its reason recorded — visible rather
        // than silently dropped.
        assertEquals("bad", q.pending(MEMBERS).first().single().recordId)
    }

    @Test
    fun `a row for an entity this build cannot send is dropped, not left to block`() = runTest {
        val dao = FakeDao()
        dao.upsert(
            PendingWrite(
                entity = "somethingElse",
                recordId = "x",
                op = PendingWrite.OP_CREATE,
                tenantId = TENANT,
                payloadJson = "{}",
                label = "?",
                queuedAt = "2026-08-08T10:00:00Z",
            ),
        )
        val q = queue(dao, emptySet())

        q.drain()

        assertNull(dao.byId("somethingElse", "x"))
    }

    // --- The one that matters ---

    @Test
    fun `a write made for another club is never sent`() = runTest {
        val dao = FakeDao()
        val handler = FakeHandler(MEMBERS)
        // Queued while signed into one club...
        queue(dao, setOf(handler), tenantId = "club-a")
            .enqueue(MEMBERS, "m1", PendingWrite.OP_CREATE, "{}", "Neu")

        // ...and drained while signed into another. A queued write outlives
        // sign-out on purpose — it is the only copy — which is exactly why the
        // drain has to check whose it is. Sending it here would create this
        // person in the wrong club.
        val sent = queue(dao, setOf(handler), tenantId = "club-b").drain()

        assertEquals(0, sent)
        assertTrue(handler.sent.isEmpty())
        // And it is still there, waiting for the account that made it.
        assertEquals("m1", dao.byId(MEMBERS, "m1")?.recordId)
    }

    @Test
    fun `the drain checks the club itself, not only the query`() = runTest {
        val dao = FakeDao()
        val handler = FakeHandler(MEMBERS)
        queue(dao, setOf(handler), tenantId = "club-a")
            .enqueue(MEMBERS, "m1", PendingWrite.OP_CREATE, "{}", "Neu")

        // Simulates the `WHERE tenantId = :tenantId` being lost in a refactor.
        // The queue must still refuse the row: this is the failure that would
        // put somebody's members into another club, and one line of SQL is too
        // thin a place for the only guard against it.
        dao.leaky = true
        val sent = queue(dao, setOf(handler), tenantId = "club-b").drain()

        assertEquals(0, sent)
        assertTrue(handler.sent.isEmpty())
    }

    @Test
    fun `nothing is queued or drained while signed out`() = runTest {
        val dao = FakeDao()
        val handler = FakeHandler(MEMBERS)
        val q = queue(dao, setOf(handler), tenantId = null)

        q.enqueue(MEMBERS, "m1", PendingWrite.OP_CREATE, "{}", "Neu")

        assertTrue(q.pending(MEMBERS).first().isEmpty())
        assertEquals(0, q.drain())
        assertEquals(0, q.count().first())
    }

    private companion object {
        const val MEMBERS = "members"
        const val TENANT = "club-a"
    }
}
