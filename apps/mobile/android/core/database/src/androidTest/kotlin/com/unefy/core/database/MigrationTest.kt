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

        helper.runMigrationsAndValidate(DB, 15, true, *DatabaseModule.ALL_MIGRATIONS).use { db ->
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

    /**
     * The club-wide entry mirror. Additive — a board member's own history lives
     * in `cached_my_entries` and must not be touched by this.
     */
    @Test
    fun migrates_from_11_to_12() {
        helper.createDatabase(DB, 11).close()

        helper.runMigrationsAndValidate(DB, 12, true, *DatabaseModule.ALL_MIGRATIONS).close()
    }

    /**
     * The cached sessions learn their own window.
     *
     * Migrated with a buffered check-in present, because that is the state a
     * real device upgrades in — a supervisor mid-evening is carrying rows that
     * exist nowhere else, and they hang off the session this table describes.
     */
    @Test
    fun migrates_from_13_to_14_keeping_cached_sessions_and_queued_check_ins() {
        helper.createDatabase(DB, 13).use { db ->
            db.execSQL(
                "INSERT INTO cached_sessions (id, title, location, recordCount) VALUES " +
                    "('s1', 'Übungsabend', 'Stand 1', 4)",
            )
            db.execSQL(
                "INSERT INTO pending_check_ins (sessionId, code, checkedInAtEpochSeconds, " +
                    "attempts) VALUES ('s1', 'uf1.AAA.1.BBB', 1783447200, 0)",
            )
        }

        helper.runMigrationsAndValidate(DB, 15, true, *DatabaseModule.ALL_MIGRATIONS).use { db ->
            db.query(
                "SELECT title, opensAtEpochSeconds, closesAtEpochSeconds FROM cached_sessions",
            ).use { cursor ->
                assertEquals(1, cursor.count)
                cursor.moveToFirst()
                assertEquals("Übungsabend", cursor.getString(0))
                // Unknown rather than wrong: the scanner offers a window-less
                // row instead of hiding it, and the next load fills it in.
                assertEquals(0L, cursor.getLong(1))
                assertEquals(0L, cursor.getLong(2))
            }
            db.query("SELECT sessionId FROM pending_check_ins").use { cursor ->
                assertEquals(1, cursor.count)
            }
        }
    }

    /**
     * The offline write queue.
     *
     * Migrating with a queued shot entry present, because that is the state a
     * real device upgrades in — an unsent row is the only copy of itself, and
     * this migration must not be the thing that loses one.
     */
    @Test
    fun migrates_from_12_to_13_without_touching_queued_work() {
        helper.createDatabase(DB, 12).use { db ->
            db.execSQL(
                "INSERT INTO pending_shot_entries (id, memberId, targetType, caliberMm, " +
                    "shotsJson, localTotal, source, recordedAt, attempts) VALUES " +
                    "('e1', 'm1', 'dsb-5', 5.6, '[]', 10, 'manual', '2026-08-08T10:00:00Z', 0)",
            )
        }

        helper.runMigrationsAndValidate(DB, 15, true, *DatabaseModule.ALL_MIGRATIONS).use { db ->
            db.query("SELECT id FROM pending_shot_entries").use { cursor ->
                assertEquals(1, cursor.count)
                cursor.moveToFirst()
                assertEquals("e1", cursor.getString(0))
            }
        }
    }

    /**
     * A record can have at most one unsent write — the primary key says so, and
     * the queue's design leans on it: editing something still queued rewrites
     * that row rather than stacking a second one behind it.
     */
    @Test
    fun the_write_queue_holds_one_row_per_record() {
        helper.createDatabase(DB, 12).close()

        helper.runMigrationsAndValidate(DB, 15, true, *DatabaseModule.ALL_MIGRATIONS).use { db ->
            val insert = "INSERT OR REPLACE INTO pending_writes (entity, recordId, op, tenantId, " +
                "payloadJson, label, queuedAt, attempts) VALUES "
            db.execSQL(insert + "('members', 'r1', 'create', 't1', '{}', 'Erst', '2026-08-08', 0)")
            db.execSQL(insert + "('members', 'r1', 'create', 't1', '{}', 'Dann', '2026-08-08', 0)")
            // Same record id, different entity — a different row, not a clash.
            db.execSQL(insert + "('events', 'r1', 'create', 't1', '{}', 'Termin', '2026-08-08', 0)")

            db.query("SELECT label FROM pending_writes WHERE entity = 'members'").use { cursor ->
                assertEquals(1, cursor.count)
                cursor.moveToFirst()
                assertEquals("Dann", cursor.getString(0))
            }
            db.query("SELECT COUNT(*) FROM pending_writes").use { cursor ->
                cursor.moveToFirst()
                assertEquals(2, cursor.getInt(0))
            }
        }
    }

    /** Every migration creates its new tables, so a fresh sync has somewhere to land. */
    @Test
    fun the_new_tables_are_empty_and_queryable_after_migrating() {
        helper.createDatabase(DB, 5).close()

        helper.runMigrationsAndValidate(DB, 15, true, *DatabaseModule.ALL_MIGRATIONS).use { db ->
            for (table in listOf(
                "synced_members",
                "sync_cursors",
                "synced_events",
                "synced_dues",
                "synced_competitions",
                "synced_competition_sessions",
                "pending_shot_entries",
                "cached_my_entries",
                "synced_entries",
                "pending_writes",
            )) {
                db.query("SELECT COUNT(*) FROM $table").use {
                    it.moveToFirst()
                    assertEquals("$table not empty", 0, it.getInt(0))
                }
            }
        }
    }

    /** The rounds mirror — a new table, nothing to carry over. */
    @Test
    fun migrates_from_14_to_15() {
        helper.createDatabase(DB, 14).close()

        helper.runMigrationsAndValidate(DB, 15, true, *DatabaseModule.ALL_MIGRATIONS).close()
    }

    private companion object {
        const val DB = "migration-test.db"
    }
}
