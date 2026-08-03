package com.unefy.feature.events

import com.unefy.core.database.SyncCursorDao
import com.unefy.core.database.SyncCursorEntity
import com.unefy.core.database.SyncedEvent
import com.unefy.core.database.SyncedEventDao
import com.unefy.core.model.Event
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The diff that decides what deserves a notification. The guards are the
 * point: announcing a whole bootstrap as "new", or a backdated event, would
 * be the first and last notification anyone allows this app.
 */
class EventsNotifierTest {

    private val now = "2026-06-01T12:00:00Z"

    @Test
    fun `a new upcoming event is announced`() = runTest {
        val harness = Harness(complete = true, rows = listOf(row("old", "2026-07-01T10:00:00Z")))
        harness.notifier.beforeDrain()

        harness.events.rows.value += row("fresh", "2026-08-01T10:00:00Z")
        harness.notifier.afterDrain()

        assertEquals(listOf("fresh"), harness.alerts.map { it.id })
    }

    /** The first drain after sign-in delivers the whole calendar — silence. */
    @Test
    fun `a bootstrap announces nothing`() = runTest {
        val harness = Harness(complete = false, rows = emptyList())
        harness.notifier.beforeDrain()

        harness.events.rows.value = listOf(
            row("a", "2026-08-01T10:00:00Z"),
            row("b", "2026-09-01T10:00:00Z"),
        )
        harness.notifier.afterDrain()

        assertEquals(emptyList<Event>(), harness.alerts)
    }

    /** A backdated or historical event is calendar hygiene, not news. */
    @Test
    fun `a new past event is not announced`() = runTest {
        val harness = Harness(complete = true, rows = emptyList())
        harness.notifier.beforeDrain()

        harness.events.rows.value = listOf(row("past", "2026-01-01T10:00:00Z"))
        harness.notifier.afterDrain()

        assertEquals(emptyList<Event>(), harness.alerts)
    }

    /** An edit to a known event is an update, not a new event. */
    @Test
    fun `an updated known event is not announced`() = runTest {
        val harness = Harness(complete = true, rows = listOf(row("known", "2026-08-01T10:00:00Z")))
        harness.notifier.beforeDrain()

        harness.events.rows.value = listOf(row("known", "2026-08-02T10:00:00Z"))
        harness.notifier.afterDrain()

        assertEquals(emptyList<Event>(), harness.alerts)
    }

    @Test
    fun `an uneventful drain stays silent`() = runTest {
        val harness = Harness(complete = true, rows = listOf(row("a", "2026-08-01T10:00:00Z")))
        harness.notifier.beforeDrain()
        harness.notifier.afterDrain()

        assertEquals(emptyList<Event>(), harness.alerts)
    }

    private inner class Harness(complete: Boolean, rows: List<SyncedEvent>) {
        val events = FakeSyncedEventDao(rows)
        val alerts = mutableListOf<Event>()
        val notifier = EventsNotifier(
            events = events,
            cursors = FakeCursors(complete),
            alerts = { alerts += it },
            clock = { now },
        )
    }

    private fun row(id: String, startsAt: String) = SyncedEvent(
        id = id,
        title = "Termin $id",
        description = null,
        eventType = null,
        location = null,
        startsAt = startsAt,
        endsAt = null,
        allDay = false,
        registrationRequired = false,
        registrationDeadline = null,
        maxParticipants = null,
        status = null,
        generation = 1,
    )
}

private class FakeSyncedEventDao(initial: List<SyncedEvent>) : SyncedEventDao {
    val rows = MutableStateFlow(initial)

    override fun all(): Flow<List<SyncedEvent>> = rows

    override suspend fun upsert(events: List<SyncedEvent>) = Unit

    override suspend fun deleteByIdsOf(ids: List<String>) = Unit

    override suspend fun sweep(generation: Long) = Unit

    override suspend fun deleteAll() = Unit
}

private class FakeCursors(private val complete: Boolean) : SyncCursorDao {
    override suspend fun get(collection: String): SyncCursorEntity? =
        SyncCursorEntity(collection, "c", bootstrapComplete = complete, generation = 1)

    override fun bootstrapCompleteStream(collection: String): Flow<Boolean> =
        MutableStateFlow(complete)

    override suspend fun upsert(cursor: SyncCursorEntity) = Unit

    override suspend fun deleteAll() = Unit
}
