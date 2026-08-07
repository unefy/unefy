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

/** The club-wide entry mirror against real SQLite. */
@RunWith(AndroidJUnit4::class)
class SyncedEntryDaoTest {

    private lateinit var database: UnefyDatabase
    private lateinit var dao: SyncedEntryDao

    @Before
    fun setUp() {
        database = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            UnefyDatabase::class.java,
        ).build()
        dao = database.syncedEntryDao()
    }

    @After
    fun tearDown() = database.close()

    /** Newest first — a club looks at this evening, not at last season. */
    @Test
    fun all_returns_newest_first() = runTest {
        dao.upsert(
            listOf(
                entry("old", recordedAt = "2026-01-04T18:00:00Z"),
                entry("new", recordedAt = "2026-08-06T19:30:00Z"),
                entry("middle", recordedAt = "2026-05-20T17:15:00Z"),
            ),
        )

        assertEquals(listOf("new", "middle", "old"), dao.all().first().map { it.id })
    }

    @Test
    fun byMember_returns_only_that_shooters_series() = runTest {
        dao.upsert(
            listOf(
                entry("a", memberId = "m1"),
                entry("b", memberId = "m2"),
                entry("c", memberId = "m1"),
            ),
        )

        assertEquals(setOf("a", "c"), dao.byMember("m1").first().mapTo(mutableSetOf()) { it.id })
    }

    /** A withdrawn series has to leave the mirror, or it stays on the bench list. */
    @Test
    fun deleteByIds_removes_tombstoned_rows() = runTest {
        dao.upsert(listOf(entry("kept"), entry("withdrawn")))

        dao.deleteByIds(listOf("withdrawn"))

        assertEquals(listOf("kept"), dao.all().first().map { it.id })
    }

    @Test
    fun sweep_drops_only_older_generations() = runTest {
        dao.upsert(
            listOf(
                entry("old").copy(generation = 1),
                entry("new").copy(generation = 2),
            ),
        )

        dao.sweep(2)

        assertEquals(listOf("new"), dao.all().first().map { it.id })
    }

    private fun entry(
        id: String,
        memberId: String = "m1",
        recordedAt: String = "2026-08-06T19:00:00Z",
    ) = SyncedEntry(
        id = id,
        sessionId = "s1",
        memberId = memberId,
        scoreValue = 91.0,
        scoreUnit = "rings",
        discipline = "GK Pistole 25m",
        targetType = "precision-25m",
        caliberMm = 9.0,
        shotsJson = null,
        innerTens = 3,
        groupingMm = 51.0,
        source = "manual",
        recordedAt = recordedAt,
        notes = null,
        generation = 1,
    )
}
