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

/**
 * The dues mirror against real SQLite. The join to `synced_members` is the part
 * worth a device test: it is what replaces the server's `member_name` merge.
 */
@RunWith(AndroidJUnit4::class)
class SyncedDueDaoTest {

    private lateinit var database: UnefyDatabase
    private lateinit var dao: SyncedDueDao

    @Before
    fun setUp() {
        database = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            UnefyDatabase::class.java,
        ).build()
        dao = database.syncedDueDao()
    }

    @After
    fun tearDown() = database.close()

    @Test
    fun the_member_name_comes_from_the_member_mirror() = runTest {
        database.syncedMemberDao().upsert(listOf(member("m1", "Anna", "Bauer")))
        dao.upsert(listOf(due("d1", memberId = "m1")))

        assertEquals("Anna Bauer", dao.withMemberNames(null).first().single().memberName)
    }

    /** A due whose member has not arrived yet must render, not crash. */
    @Test
    fun a_due_without_a_mirrored_member_gets_an_empty_name() = runTest {
        dao.upsert(listOf(due("d1", memberId = "missing")))

        assertEquals("", dao.withMemberNames(null).first().single().memberName)
    }

    /** The local replacement for the server-side chip filter. */
    @Test
    fun the_status_filter_matches_exactly() = runTest {
        dao.upsert(
            listOf(
                due("open", status = "open"),
                due("paid", status = "paid"),
                due("cancelled", status = "cancelled"),
            ),
        )

        assertEquals(listOf("open"), dao.withMemberNames("open").first().map { it.id })
        assertEquals(3, dao.withMemberNames(null).first().size)
    }

    @Test
    fun newest_due_date_first_and_null_dates_last() = runTest {
        dao.upsert(
            listOf(
                due("old", dueDate = "2026-01-31"),
                due("none", dueDate = null),
                due("new", dueDate = "2026-06-30"),
            ),
        )

        assertEquals(listOf("new", "old", "none"), dao.withMemberNames(null).first().map { it.id })
    }

    @Test
    fun sweep_drops_only_older_generations() = runTest {
        dao.upsert(listOf(due("old").copy(generation = 1), due("new").copy(generation = 2)))

        dao.sweep(2)

        assertEquals(listOf("new"), dao.withMemberNames(null).first().map { it.id })
    }

    private fun due(
        id: String,
        memberId: String = "m-$id",
        status: String? = "open",
        dueDate: String? = "2026-01-31",
    ) = SyncedDue(
        id = id,
        memberId = memberId,
        feeName = "Erwachsene",
        amount = "120.00",
        dueDate = dueDate,
        status = status,
        paidAt = null,
        generation = 1,
    )

    private fun member(id: String, firstName: String, lastName: String) = SyncedMember(
        id = id,
        memberNumber = "M-$id",
        firstName = firstName,
        lastName = lastName,
        email = null,
        phone = null,
        mobile = null,
        birthday = null,
        street = null,
        zipCode = null,
        city = null,
        status = null,
        category = null,
        joinedAt = "2024-01-01",
        leftAt = null,
        generation = 1,
    )
}
