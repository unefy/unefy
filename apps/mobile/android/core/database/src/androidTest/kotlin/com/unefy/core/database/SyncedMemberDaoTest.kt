package com.unefy.core.database

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * The member mirror against real SQLite.
 *
 * On a device rather than the JVM because what is being tested *is* SQLite: how
 * `LIKE` folds case, what `ORDER BY` does with an umlaut, and whether a
 * transaction rolls back. A fake DAO would agree with whatever the fake was
 * written to believe.
 */
@RunWith(AndroidJUnit4::class)
class SyncedMemberDaoTest {

    private lateinit var database: UnefyDatabase
    private lateinit var dao: SyncedMemberDao

    @Before
    fun setUp() {
        database = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            UnefyDatabase::class.java,
        ).build()
        dao = database.syncedMemberDao()
    }

    @After
    fun tearDown() = database.close()

    @Test
    fun search_with_an_empty_query_returns_everyone_sorted_by_surname() = runTest {
        dao.upsert(listOf(member("1", "Zimmermann"), member("2", "Ähnlich"), member("3", "Bauer")))

        assertEquals(
            listOf("Ähnlich", "Bauer", "Zimmermann"),
            dao.search("").first().map { it.lastName },
        )
    }

    /**
     * The whole reason `sortKey` exists. Ordering by `lastName` directly would put
     * "Ähnlich" after "Zimmermann", because SQLite compares UTF-8 bytes and "Ä"
     * is not near "A".
     */
    @Test
    fun an_umlaut_surname_sorts_where_a_German_reader_expects_it() = runTest {
        dao.upsert(listOf(member("1", "Arnold"), member("2", "Ähnlich"), member("3", "Baum")))

        assertEquals(
            listOf("Ähnlich", "Arnold", "Baum"),
            dao.search("").first().map { it.lastName },
        )
    }

    @Test
    fun search_ignores_case_across_umlauts() = runTest {
        dao.upsert(listOf(member("1", "Müller"), member("2", "Bauer")))

        assertEquals(listOf("Müller"), dao.search("MÜLL").first().map { it.lastName })
    }

    /** Typing without the umlaut is what people actually do. */
    @Test
    fun search_finds_an_umlaut_name_typed_in_plain_ascii() = runTest {
        dao.upsert(listOf(member("1", "Müller"), member("2", "Bauer")))

        assertEquals(listOf("Müller"), dao.search("muller").first().map { it.lastName })
    }

    @Test
    fun search_matches_the_member_number() = runTest {
        dao.upsert(listOf(member("1", "Bauer", number = "0815"), member("2", "Krause")))

        assertEquals(listOf("Bauer"), dao.search("0815").first().map { it.lastName })
    }

    @Test
    fun upsert_replaces_a_row_and_its_derived_keys() = runTest {
        dao.upsert(listOf(member("1", "Müller")))
        dao.upsert(listOf(member("1", "Schmidt")))

        val rows = dao.search("").first()
        assertEquals(1, rows.size)
        assertEquals("schmidt vorname", rows.single().sortKey)
        assertEquals(emptyList<String>(), dao.search("muller").first().map { it.id })
    }

    @Test
    fun deleteByIds_removes_the_tombstoned_rows_only() = runTest {
        dao.upsert(listOf(member("1", "Bauer"), member("2", "Krause"), member("3", "Lang")))

        dao.deleteByIds(listOf("1", "3"))

        assertEquals(listOf("2"), dao.search("").first().map { it.id })
    }

    /**
     * `IN ()` is not valid SQL and Room expands the list literally, so an empty
     * page has to be caught before the query. A page of pure changes with no
     * deletions is the ordinary case, not an edge one.
     */
    @Test
    fun deleteByIds_with_nothing_to_delete_leaves_the_table_alone() = runTest {
        dao.upsert(listOf(member("1", "Bauer")))

        dao.deleteByIds(emptyList())

        assertEquals(listOf("1"), dao.search("").first().map { it.id })
    }

    /**
     * Hard-deleted rows are the ones sync can never report. A re-bootstrap stamps
     * everything it sees with a new generation; whatever still carries the old one
     * is gone upstream.
     */
    @Test
    fun sweep_drops_rows_an_earlier_generation_left_behind() = runTest {
        dao.upsert(listOf(member("1", "Bauer", generation = 1), member("2", "Krause", generation = 1)))
        dao.upsert(listOf(member("1", "Bauer", generation = 2)))

        dao.sweep(generation = 2)

        assertEquals(listOf("1"), dao.search("").first().map { it.id })
    }

    @Test
    fun countStream_counts_the_whole_club_not_the_filtered_list() = runTest {
        dao.upsert(listOf(member("1", "Bauer"), member("2", "Krause")))

        assertEquals(2, dao.countStream().first())
    }

    @Test
    fun byIdStream_is_null_for_a_member_that_is_not_mirrored() = runTest {
        dao.upsert(listOf(member("1", "Bauer")))

        assertEquals("Bauer", dao.byIdStream("1").first()?.lastName)
        assertNull(dao.byIdStream("nope").first())
    }

    private fun member(
        id: String,
        lastName: String,
        number: String = "000$id",
        generation: Long = 1,
    ) = SyncedMember(
        id = id,
        memberNumber = number,
        firstName = "Vorname",
        lastName = lastName,
        email = null,
        phone = null,
        mobile = null,
        birthday = null,
        street = null,
        zipCode = null,
        city = null,
        status = "active",
        category = null,
        joinedAt = "2020-01-01",
        leftAt = null,
        generation = generation,
    )
}
