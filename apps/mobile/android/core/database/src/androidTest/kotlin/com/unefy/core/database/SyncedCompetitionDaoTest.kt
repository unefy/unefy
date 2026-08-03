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

/** The competition mirror against real SQLite. */
@RunWith(AndroidJUnit4::class)
class SyncedCompetitionDaoTest {

    private lateinit var database: UnefyDatabase
    private lateinit var dao: SyncedCompetitionDao

    @Before
    fun setUp() {
        database = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            UnefyDatabase::class.java,
        ).build()
        dao = database.syncedCompetitionDao()
    }

    @After
    fun tearDown() = database.close()

    /** Newest first — replaces the `sortedByDescending` the ViewModel used to do. */
    @Test
    fun all_returns_newest_start_date_first() = runTest {
        dao.upsert(
            listOf(
                competition("old", startDate = "2025-01-01"),
                competition("new", startDate = "2026-06-01"),
                competition("middle", startDate = "2025-09-01"),
            ),
        )

        assertEquals(listOf("new", "middle", "old"), dao.all().first().map { it.id })
    }

    @Test
    fun sweep_drops_only_older_generations() = runTest {
        dao.upsert(
            listOf(
                competition("old").copy(generation = 1),
                competition("new").copy(generation = 2),
            ),
        )

        dao.sweep(2)

        assertEquals(listOf("new"), dao.all().first().map { it.id })
    }

    private fun competition(id: String, startDate: String = "2026-01-01") = SyncedCompetition(
        id = id,
        name = "Vereinsmeisterschaft $id",
        description = null,
        competitionType = null,
        startDate = startDate,
        endDate = null,
        scoringUnit = "Ringe",
        scoringMode = "highest_wins",
        disciplines = "",
        generation = 1,
    )
}
