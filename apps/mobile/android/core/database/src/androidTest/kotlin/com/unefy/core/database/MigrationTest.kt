package com.unefy.core.database

import androidx.room.testing.MigrationTestHelper
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * That a phone holding the previous database can open the new one.
 *
 * Worth a test because the failure mode is asymmetric: a fresh install never runs
 * a migration, so a broken one is invisible to everyone developing the app and
 * hits only devices that already had it. `runMigrationsAndValidate` compares the
 * result against the checked-in schema JSON, which is what catches a hand-written
 * `CREATE TABLE` that drifted from the entity.
 *
 * The migrations come from [DatabaseModule.ALL_MIGRATIONS] rather than being
 * listed here again — a second copy would pass while the app still crashed.
 */
@RunWith(AndroidJUnit4::class)
class MigrationTest {

    @get:Rule
    val helper = MigrationTestHelper(
        InstrumentationRegistry.getInstrumentation(),
        UnefyDatabase::class.java,
    )

    /** The mirror and the cursor table are additive, so nothing has to survive. */
    @Test
    fun migrates_from_5_to_6() {
        helper.createDatabase(DB, 5).close()

        helper.runMigrationsAndValidate(DB, 6, true, *DatabaseModule.ALL_MIGRATIONS).close()
    }

    /** The three list mirrors are additive too. */
    @Test
    fun migrates_from_6_to_7() {
        helper.createDatabase(DB, 6).close()

        helper.runMigrationsAndValidate(DB, 7, true, *DatabaseModule.ALL_MIGRATIONS).close()
    }

    /** The queue's client id column — nullable, so old queued rows still drain. */
    @Test
    fun migrates_from_7_to_8() {
        helper.createDatabase(DB, 7).close()

        helper.runMigrationsAndValidate(DB, 8, true, *DatabaseModule.ALL_MIGRATIONS).close()
    }

    /** Drops the retired member cache; the pick list reads the mirror now. */
    @Test
    fun migrates_from_8_to_9() {
        helper.createDatabase(DB, 8).close()

        helper.runMigrationsAndValidate(DB, 9, true, *DatabaseModule.ALL_MIGRATIONS).close()
    }

    /**
     * A queued check-in exists nowhere else, so the one thing the chain must
     * not do is lose one. Pinned rather than assumed — the 4→5 migration already
     * drops and recreates a *cache* table, and the difference between the two is
     * the whole reason there is no destructive fallback. Runs to the newest
     * version so every future migration stays covered.
     */
    @Test
    fun a_queued_check_in_survives_the_migration() {
        helper.createDatabase(DB, 5).use { db ->
            db.execSQL(
                """
                INSERT INTO pending_check_ins (sessionId, code, checkedInAtEpochSeconds, attempts)
                VALUES ('session-1', 'CODE-1', 1735689600, 0)
                """,
            )
        }

        helper.runMigrationsAndValidate(DB, 11, true, *DatabaseModule.ALL_MIGRATIONS).use { db ->
            db.query("SELECT sessionId, code FROM pending_check_ins").use { cursor ->
                assertEquals(1, cursor.count)
                cursor.moveToFirst()
                assertEquals("session-1", cursor.getString(0))
                assertEquals("CODE-1", cursor.getString(1))
            }
        }
    }

    /** The member's gender column. */
    @Test
    fun migrates_from_9_to_10() {
        helper.createDatabase(DB, 9).close()

        helper.runMigrationsAndValidate(DB, 10, true, *DatabaseModule.ALL_MIGRATIONS).close()
    }

    /** The shot queue and the member's own history — both additive. */
    @Test
    fun migrates_from_10_to_11() {
        helper.createDatabase(DB, 10).close()

        helper.runMigrationsAndValidate(DB, 11, true, *DatabaseModule.ALL_MIGRATIONS).close()
    }

    /** Every migration creates its new tables, so a fresh sync has somewhere to land. */
    @Test
    fun the_new_tables_are_empty_and_queryable_after_migrating() {
        helper.createDatabase(DB, 5).close()

        helper.runMigrationsAndValidate(DB, 11, true, *DatabaseModule.ALL_MIGRATIONS).use { db ->
            for (table in listOf(
                "synced_members",
                "sync_cursors",
                "synced_events",
                "synced_dues",
                "synced_competitions",
                "pending_shot_entries",
                "cached_my_entries",
            )) {
                db.query("SELECT COUNT(*) FROM $table").use {
                    it.moveToFirst()
                    assertEquals("$table not empty", 0, it.getInt(0))
                }
            }
        }
    }

    private companion object {
        const val DB = "migration-test.db"
    }
}
