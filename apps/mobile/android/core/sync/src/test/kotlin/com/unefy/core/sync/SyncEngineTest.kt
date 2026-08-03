package com.unefy.core.sync

import com.unefy.core.database.SyncCursorDao
import com.unefy.core.database.SyncCursorEntity
import com.unefy.core.database.SyncTransaction
import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiError
import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.respond
import io.ktor.client.engine.mock.respondError
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.http.ContentType
import io.ktor.http.HttpStatusCode
import io.ktor.http.headersOf
import io.ktor.serialization.kotlinx.json.json
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The drain loop, against a real Ktor client on a mock engine.
 *
 * A mock engine rather than a stubbed [ApiClient] because two of the things worth
 * testing live in the decoding: that the sync envelope — `data` as an object,
 * `meta.sync` nested a level deeper than every other route — is read correctly at
 * all, and that a 409 is recognised. A hand-written fake would have agreed with
 * whatever it was told to return.
 */
class SyncEngineTest {

    @Test
    fun `a single page drains and stores the cursor`() = runTest {
        val engine = engineFor(page(ids = listOf("a", "b"), cursor = "c1", hasMore = false))
        val collection = RecordingCollection()

        assertEquals(SyncOutcome.UpToDate, engine.sync(collection))
        assertEquals(listOf("a", "b"), collection.upserted)
        assertEquals("c1", engine.cursors.get("members")?.cursor)
        assertTrue(engine.cursors.get("members")!!.bootstrapComplete)
    }

    /**
     * The point of paging: the cursor from page one has to come back as the query
     * for page two, or the drain reads the same page forever.
     */
    @Test
    fun `a multi-page drain follows the cursor it was handed`() = runTest {
        val engine = engineFor(
            page(ids = listOf("a"), cursor = "c1", hasMore = true),
            page(ids = listOf("b"), cursor = "c2", hasMore = false),
        )
        val collection = RecordingCollection()

        assertEquals(SyncOutcome.UpToDate, engine.sync(collection))
        assertEquals(listOf("a", "b"), collection.upserted)
        // Page one goes out with no cursor; page two with the one page one returned.
        assertEquals(listOf(null, "c1"), engine.requestedCursors)
        assertEquals("c2", engine.cursors.get("members")?.cursor)
    }

    @Test
    fun `tombstones are applied as deletions`() = runTest {
        val engine = engineFor(
            page(ids = listOf("a"), deletedIds = listOf("gone"), cursor = "c1", hasMore = false),
        )
        val collection = RecordingCollection()

        engine.sync(collection)

        assertEquals(listOf("a"), collection.upserted)
        assertEquals(listOf("gone"), collection.deleted)
    }

    /**
     * The client half of "a page is a superset, never a subset". If the cursor
     * moved but the rows did not land, the server would never resend them.
     *
     * And the failure is *reported*, never thrown: an apply that throws — a
     * decode drift, a full disk — used to propagate out of the coordinator's
     * serving loop and silently stop every collection's sync for the rest of
     * the session. Found on the device: a null `member_name` in the dues
     * payload left events and competitions unsynced too.
     */
    @Test
    fun `a page that fails to apply advances no cursor and reports the failure`() = runTest {
        val engine = engineFor(page(ids = listOf("a"), cursor = "c1", hasMore = false))
        val collection = RecordingCollection(failOnApply = true)

        val outcome = engine.sync(collection)

        assertTrue(outcome is SyncOutcome.Failed)
        assertNull(engine.cursors.get("members"))
    }

    /**
     * The rollback itself is Room's, and this cannot test it — what it can test is
     * the thing Room needs in order to provide it: that both writes happen inside
     * one transaction block. Moving the cursor write out would still pass every
     * other test here and would reintroduce the hole.
     */
    @Test
    fun `rows and cursor are written inside one transaction`() = runTest {
        val engine = engineFor(page(ids = listOf("a"), cursor = "c1", hasMore = false))

        engine.sync(RecordingCollection())

        assertEquals(1, engine.transaction.blocks)
        assertTrue("the cursor was stored outside the transaction", engine.cursors.wroteInside)
    }

    /** Same rule for a network failure: the stored position must not move. */
    @Test
    fun `a network failure leaves the stored cursor where it was`() = runTest {
        val engine = engineFor(
            page(ids = listOf("a"), cursor = "c1", hasMore = true),
            null, // the second page never arrives
        )
        val collection = RecordingCollection()

        val outcome = engine.sync(collection)

        assertTrue(outcome is SyncOutcome.Failed)
        assertTrue((outcome as SyncOutcome.Failed).error is ApiError.Network)
        assertEquals("c1", engine.cursors.get("members")?.cursor)
        assertEquals(listOf("a"), collection.upserted)
    }

    /**
     * A rejected cursor is the only recovery path for rows that were hard-deleted
     * upstream — no tombstone can report those. The re-read stamps a new
     * generation and sweeps whatever it does not mention.
     */
    @Test
    fun `a cursor the server rejects triggers a re-bootstrap that sweeps`() = runTest {
        val engine = engineFor(
            page(ids = listOf("a"), cursor = "c1", hasMore = false),
            HttpStatusCode.Conflict,
            page(ids = listOf("a"), cursor = "c2", hasMore = false),
        )
        val collection = RecordingCollection()

        assertEquals(SyncOutcome.UpToDate, engine.sync(collection))
        val afterFirst = engine.cursors.get("members")!!
        assertEquals(1L, afterFirst.generation)
        // The first bootstrap sweeps too. It has nothing to find, and demanding
        // that it skip would mean a second rule for a case that is already correct.
        assertEquals(listOf(1L), collection.swept)

        assertEquals(SyncOutcome.UpToDate, engine.sync(collection))

        val afterRestart = engine.cursors.get("members")!!
        assertEquals(2L, afterRestart.generation)
        assertEquals("c2", afterRestart.cursor)
        // Swept with the new generation, so rows the re-read did not mention go.
        assertEquals(listOf(1L, 2L), collection.swept)
    }

    /** A broken or foreign cursor recovers the same way, and never as a 500. */
    @Test
    fun `a cursor the server cannot parse also re-bootstraps`() = runTest {
        val engine = engineFor(
            page(ids = listOf("a"), cursor = "c1", hasMore = false),
            HttpStatusCode.BadRequest,
            page(ids = listOf("a"), cursor = "c2", hasMore = false),
        )
        val collection = RecordingCollection()

        engine.sync(collection)
        assertEquals(SyncOutcome.UpToDate, engine.sync(collection))
        assertEquals(2L, engine.cursors.get("members")?.generation)
    }

    /** Twice in a row is a server that will not accept anything, not a stale cursor. */
    @Test
    fun `a second rejection reports a failure instead of restarting again`() = runTest {
        val engine = engineFor(HttpStatusCode.Conflict, HttpStatusCode.Conflict)
        val collection = RecordingCollection()

        val outcome = engine.sync(collection)

        assertTrue(outcome is SyncOutcome.Failed)
        assertEquals(emptyList<Long>(), collection.swept)
    }

    /**
     * A plain member may not mirror the member list. Reported separately from a
     * failure because retrying it on every doorbell would be pointless traffic
     * for an answer that cannot change.
     */
    @Test
    fun `a forbidden collection is reported as not permitted`() = runTest {
        val engine = engineFor(HttpStatusCode.Forbidden)
        val collection = RecordingCollection()

        assertEquals(SyncOutcome.NotPermitted, engine.sync(collection))
        assertNull(engine.cursors.get("members"))
    }

    /**
     * A steady-state delta must not sweep: it only sees what changed, so sweeping
     * would delete every member who simply had not been edited.
     */
    @Test
    fun `a delta after a completed bootstrap never sweeps`() = runTest {
        val engine = engineFor(
            page(ids = listOf("a", "b"), cursor = "c1", hasMore = false),
            page(ids = listOf("a"), cursor = "c2", hasMore = false),
        )
        val collection = RecordingCollection()

        engine.sync(collection)
        collection.swept.clear()
        engine.sync(collection)

        assertEquals(emptyList<Long>(), collection.swept)
        assertEquals(1L, engine.cursors.get("members")?.generation)
    }

    /**
     * A bootstrap the user killed halfway resumes from its cursor — and is still a
     * bootstrap, so it sweeps when it finally reaches the end. Deriving "is this a
     * bootstrap" from "did this call start without a cursor" would lose that.
     */
    @Test
    fun `an interrupted bootstrap still sweeps when it finishes`() = runTest {
        val first = engineFor(
            page(ids = listOf("a"), cursor = "c1", hasMore = true),
            null, // killed mid-drain
        )
        val collection = RecordingCollection()
        first.sync(collection)
        assertEquals(false, first.cursors.get("members")?.bootstrapComplete)
        assertEquals(emptyList<Long>(), collection.swept)

        val resumed = engineFor(
            page(ids = listOf("b"), cursor = "c2", hasMore = false),
            cursors = first.cursors,
        )
        resumed.sync(collection)

        assertEquals(listOf(1L), collection.swept)
        assertEquals(true, resumed.cursors.get("members")?.bootstrapComplete)
    }

    /**
     * The regression test for stopping on emptiness. During a bootstrap the
     * server filters tombstones out of the body *after* applying its scan limit,
     * so a stretch of two hundred deletions arrives as an empty page whose
     * cursor still moves and whose `has_more` is still true. Treating that as
     * the end of the feed stranded everyone sorted behind the stretch outside
     * the mirror — and marked the bootstrap complete on top.
     */
    @Test
    fun `an empty page with a moving cursor keeps draining`() = runTest {
        val engine = engineFor(
            page(ids = emptyList(), cursor = "c1", hasMore = true),
            page(ids = listOf("a"), cursor = "c2", hasMore = false),
        )
        val collection = RecordingCollection()

        assertEquals(SyncOutcome.UpToDate, engine.sync(collection))
        assertEquals(listOf("a"), collection.upserted)
        assertEquals(listOf(null, "c1"), engine.requestedCursors)
        assertEquals("c2", engine.cursors.get("members")?.cursor)
    }

    /**
     * What genuinely cannot be right is `has_more` with an *unmoved* cursor —
     * asking again would fetch the identical page. Treating that as the end is
     * what stops a server-side bug from spinning this loop forever.
     */
    @Test
    fun `a page that makes no progress ends the drain`() = runTest {
        val engine = engineFor(
            page(ids = listOf("a"), cursor = "c1", hasMore = true),
            page(ids = listOf("a"), cursor = "c1", hasMore = true),
        )
        val collection = RecordingCollection()

        assertEquals(SyncOutcome.UpToDate, engine.sync(collection))
        assertEquals(2, engine.requestedCursors.size)
    }
}

// ---------------------------------------------------------------------------
// Harness
// ---------------------------------------------------------------------------

private class TestEngine(
    val engine: SyncEngine,
    val cursors: FakeSyncCursorDao,
    val transaction: CountingTransaction,
    val requestedCursors: List<String?>,
) {
    suspend fun sync(collection: SyncCollection) = engine.sync(collection)
}

/**
 * Builds an engine whose backend answers with [responses] in order.
 *
 * A response may be a [String] body, an [HttpStatusCode] to fail with, or null to
 * fail the connection — the three shapes the drain has to tell apart.
 */
private fun engineFor(
    vararg responses: Any?,
    cursors: FakeSyncCursorDao = FakeSyncCursorDao(),
): TestEngine {
    val requested = mutableListOf<String?>()
    var index = 0

    val mock = MockEngine { request ->
        requested += request.url.parameters["cursor"]
        when (val response = responses.getOrNull(index++)) {
            null -> throw java.io.IOException("no connection")
            is HttpStatusCode -> respondError(response)
            is String -> respond(
                content = response,
                headers = headersOf("Content-Type", ContentType.Application.Json.toString()),
            )
            else -> error("unsupported response $response")
        }
    }

    val client = HttpClient(mock) {
        expectSuccess = false
        install(ContentNegotiation) {
            json(Json { ignoreUnknownKeys = true; explicitNulls = false })
        }
    }

    val transaction = CountingTransaction()
    cursors.transaction = transaction

    return TestEngine(
        engine = DeltaSyncEngine(ApiClient(client), cursors, transaction),
        cursors = cursors,
        transaction = transaction,
        requestedCursors = requested,
    )
}

/** A sync page as the backend actually spells it. */
private fun page(
    ids: List<String>,
    deletedIds: List<String> = emptyList(),
    cursor: String,
    hasMore: Boolean,
): String {
    val changed = ids.joinToString(",") { """{"id":"$it","first_name":"A","last_name":"B"}""" }
    val deleted = deletedIds.joinToString(",") {
        """{"id":"$it","deleted_at":"2026-08-03T10:00:00Z"}"""
    }
    return """
        {"data":{"changed":[$changed],"deleted":[$deleted]},
         "meta":{"sync":{"cursor":"$cursor","has_more":$hasMore,
                         "server_time":"2026-08-03T10:00:00Z","collection":"members"}}}
    """.trimIndent()
}

/**
 * Runs the block straight through, and remembers whether it is inside one.
 *
 * The depth is what lets a test assert that the cursor write is *inside* the
 * transaction — the property Room turns into atomicity, and the one a later
 * refactor could quietly drop.
 */
private class CountingTransaction : SyncTransaction {
    var blocks = 0
    var depth = 0

    override suspend fun <T> immediate(block: suspend () -> T): T {
        blocks++
        depth++
        try {
            return block()
        } finally {
            depth--
        }
    }
}

/** An in-memory stand-in for the Room DAO. */
private class FakeSyncCursorDao : SyncCursorDao {
    private val rows = mutableMapOf<String, SyncCursorEntity>()

    var transaction: CountingTransaction? = null
    var wroteInside = false
        private set

    override suspend fun get(collection: String): SyncCursorEntity? = rows[collection]

    override fun bootstrapCompleteStream(collection: String): Flow<Boolean> =
        flowOf(rows[collection]?.bootstrapComplete == true)

    override suspend fun upsert(cursor: SyncCursorEntity) {
        wroteInside = (transaction?.depth ?: 0) > 0
        rows[cursor.collection] = cursor
    }

    override suspend fun deleteAll() = rows.clear()
}

private class RecordingCollection(
    private val failOnApply: Boolean = false,
) : SyncCollection {
    override val name = "members"

    val upserted = mutableListOf<String>()
    val deleted = mutableListOf<String>()
    val swept = mutableListOf<Long>()
    var cleared = false

    override suspend fun apply(changed: List<JsonElement>, deleted: List<String>, generation: Long) {
        if (failOnApply) throw IllegalStateException("disk full")
        upserted += changed.map { it.jsonObject.getValue("id").jsonPrimitive.content }
        this.deleted += deleted
    }

    override suspend fun sweep(generation: Long) {
        swept += generation
    }

    override suspend fun clear() {
        cleared = true
    }
}
