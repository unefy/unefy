package com.unefy.core.database

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/** The event mirror against real SQLite — ordering and sweep are its whole job. */
@RunWith(AndroidJUnit4::class)
class SyncedEventDaoTest {

    private lateinit var database: UnefyDatabase
    private lateinit var dao: SyncedEventDao

    @Before
    fun setUp() {
        database = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            UnefyDatabase::class.java,
        ).build()
        dao = database.syncedEventDao()
    }

    @After
    fun tearDown() = database.close()

    /** Ascending by start — the ViewModel derives both sections from this one order. */
    @Test
    fun all_returns_events_in_start_order() = runTest {
        dao.upsert(
            listOf(
                event("late", startsAt = "2026-09-01T10:00:00Z"),
                event("early", startsAt = "2026-07-01T10:00:00Z"),
                event("middle", startsAt = "2026-08-01T10:00:00Z"),
            ),
        )

        assertEquals(listOf("early", "middle", "late"), dao.all().first().map { it.id })
    }

    @Test
    fun tombstones_delete_and_an_empty_list_is_a_no_op() = runTest {
        dao.upsert(listOf(event("keep"), event("gone")))

        dao.deleteByIds(emptyList())
        dao.deleteByIds(listOf("gone"))

        assertEquals(listOf("keep"), dao.all().first().map { it.id })
    }

    @Test
    fun sweep_drops_only_older_generations() = runTest {
        dao.upsert(listOf(event("old").copy(generation = 1), event("new").copy(generation = 2)))

        dao.sweep(2)

        assertEquals(listOf("new"), dao.all().first().map { it.id })
    }

    private fun event(id: String, startsAt: String = "2026-08-01T10:00:00Z") = SyncedEvent(
        id = id,
        title = "Training $id",
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
