package com.unefy.core.sync

import com.unefy.core.database.SyncCursorDao
import com.unefy.core.database.SyncCursorEntity
import com.unefy.core.database.SyncTransaction
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonElement
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What has to be gone when an account leaves the phone.
 *
 * The rows are the obvious half — the next person signing in must not see the
 * previous club's members. The cursor is the half that is easy to forget and
 * expensive to get wrong, because keeping it does not look like a leak: the mirror
 * simply stays wrong, quietly, for as long as the server still accepts the token.
 */
class SyncSignOutTest {

    @Test
    fun `sign-out clears the rows and the cursor`() = runTest {
        val collection = ClearableCollection()
        val cursors = FakeCursors().apply {
            upsert(SyncCursorEntity("members", "c1", bootstrapComplete = true, generation = 1))
        }
        val signOut = signOut(collection, cursors)

        signOut.onSignOut()

        assertTrue(collection.cleared)
        assertNull(cursors.get("members"))
    }

    /**
     * Together or not at all.
     *
     * Rows without the cursor means the next sync is a delta into an empty mirror —
     * a member list that stays nearly empty until the cursor ages out. Cursor
     * without the rows means the next bootstrap stamps generation 1 and sweeps
     * nothing, so the old club's members stay on the phone.
     */
    @Test
    fun `clearing happens in one transaction`() = runTest {
        val transaction = DepthTrackingTransaction()
        val collection = ClearableCollection(transaction)
        val cursors = FakeCursors(transaction)
        signOut(collection, cursors, transaction).onSignOut()

        assertEquals(1, transaction.blocks)
        assertTrue("rows were cleared outside the transaction", collection.clearedInside)
        assertTrue("the cursor was cleared outside the transaction", cursors.clearedInside)
    }

    /** Every registered collection, so a feature added later is covered by default. */
    @Test
    fun `sign-out clears every registered collection`() = runTest {
        val members = ClearableCollection(name = "members")
        val events = ClearableCollection(name = "events")
        val signOut = SyncSignOut(
            collections = setOf(members, events),
            cursors = FakeCursors(),
            coordinator = RecordingCoordinator(),
            transaction = DepthTrackingTransaction(),
        )

        signOut.onSignOut()

        assertTrue(members.cleared)
        assertTrue(events.cleared)
    }

    /**
     * The coordinator is a singleton that outlives the account, so a refusal it
     * learned from one role must not follow the next person in.
     */
    @Test
    fun `sign-out resets the coordinator's latched verdicts`() = runTest {
        val coordinator = RecordingCoordinator()
        SyncSignOut(
            collections = setOf(ClearableCollection()),
            cursors = FakeCursors(),
            coordinator = coordinator,
            transaction = DepthTrackingTransaction(),
        ).onSignOut()

        assertTrue(coordinator.forgotten)
    }

    private fun signOut(
        collection: SyncCollection,
        cursors: SyncCursorDao,
        transaction: SyncTransaction = DepthTrackingTransaction(),
    ) = SyncSignOut(setOf(collection), cursors, RecordingCoordinator(), transaction)
}

private class DepthTrackingTransaction : SyncTransaction {
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

private class ClearableCollection(
    private val transaction: DepthTrackingTransaction? = null,
    override val name: String = "members",
) : SyncCollection {
    var cleared = false
    var clearedInside = false

    override suspend fun apply(
        changed: List<JsonElement>,
        deleted: List<String>,
        generation: Long,
    ) = Unit

    override suspend fun sweep(generation: Long) = Unit

    override suspend fun clear() {
        cleared = true
        clearedInside = (transaction?.depth ?: 0) > 0
    }
}

private class FakeCursors(
    private val transaction: DepthTrackingTransaction? = null,
) : SyncCursorDao {
    private val rows = mutableMapOf<String, SyncCursorEntity>()
    var clearedInside = false

    override suspend fun get(collection: String) = rows[collection]
    override fun bootstrapCompleteStream(collection: String): Flow<Boolean> =
        flowOf(rows[collection]?.bootstrapComplete == true)

    override suspend fun upsert(cursor: SyncCursorEntity) {
        rows[cursor.collection] = cursor
    }

    override suspend fun deleteAll() {
        clearedInside = (transaction?.depth ?: 0) > 0
        rows.clear()
    }
}

private class RecordingCoordinator : SyncCoordinator {
    override fun signals(entity: String): Flow<ChangeHint> = emptyFlow()

    var forgotten = false

    override fun status(collection: String): Flow<SyncStatus> = flowOf(SyncStatus.Idle)
    override suspend fun request(collection: String) = Unit
    override suspend fun requestAll() = Unit
    override suspend fun syncNow(collection: String) = Unit
    override suspend fun run() = Unit
    override fun forgetStatuses() {
        forgotten = true
    }
}
