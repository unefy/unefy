package com.unefy.core.database

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.SQLiteConnection
import androidx.sqlite.execSQL
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * The app's local database.
 *
 * Two kinds of table, and the difference matters. The attendance session/record
 * tables are *caches*: refreshed from whatever a list call returned, read only
 * when the network refuses, prunable with `retainOnly`. The `synced_*` tables
 * are a *mirror*: filled by delta-sync, the only thing the list screens read,
 * and emptied only by sign-out.
 *
 * No `fallbackToDestructiveMigration`. The queue holds check-ins that exist
 * nowhere else until they sync, and dropping the table on a schema change would
 * silently lose an evening's attendance.
 */
@Database(
    entities = [
        PendingCheckIn::class,
        CachedSession::class,
        CachedSessionRecord::class,
        SyncedMember::class,
        SyncedEvent::class,
        SyncedDue::class,
        SyncedCompetition::class,
        PendingShotEntry::class,
        CachedShotEntry::class,
        SyncCursorEntity::class,
    ],
    version = 11,
    exportSchema = true,
)
abstract class UnefyDatabase : RoomDatabase() {
    abstract fun pendingCheckInDao(): PendingCheckInDao

    abstract fun cachedSessionDao(): CachedSessionDao

    abstract fun cachedSessionRecordDao(): CachedSessionRecordDao

    abstract fun syncedMemberDao(): SyncedMemberDao

    abstract fun syncedEventDao(): SyncedEventDao

    abstract fun syncedDueDao(): SyncedDueDao

    abstract fun syncedCompetitionDao(): SyncedCompetitionDao

    abstract fun pendingShotEntryDao(): PendingShotEntryDao

    abstract fun cachedShotEntryDao(): CachedShotEntryDao

    abstract fun syncCursorDao(): SyncCursorDao
}

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): UnefyDatabase =
        Room.databaseBuilder(context, UnefyDatabase::class.java, DATABASE_NAME)
            .addMigrations(*ALL_MIGRATIONS)
            .build()

    /**
     * Every migration, in one list.
     *
     * One place rather than a call-site argument list, so a new migration cannot
     * be written and then left out of the builder — a mistake that costs nothing
     * on a fresh install and crashes every upgrading device. `internal` so the
     * migration test can hand the same list to `MigrationTestHelper` instead of
     * keeping a second copy that could drift.
     */
    internal val ALL_MIGRATIONS: Array<Migration> by lazy {
        arrayOf(
            MIGRATION_1_2,
            MIGRATION_2_3,
            MIGRATION_3_4,
            MIGRATION_4_5,
            MIGRATION_5_6,
            MIGRATION_6_7,
            MIGRATION_7_8,
            MIGRATION_8_9,
            MIGRATION_9_10,
            MIGRATION_10_11,
        )
    }

    /**
     * Adds the two caches.
     *
     * `IF NOT EXISTS` because version 1 shipped in more than one shape during
     * development — first the queue alone, then the queue plus members — and a
     * device may hold either. Room only noticed because the identity hash
     * differed; without this a phone with the older file crashes on open.
     *
     * A destructive fallback would have been one line, and would have thrown
     * away queued check-ins that exist nowhere else.
     */
    private val MIGRATION_1_2 = object : Migration(1, 2) {
        override fun migrate(connection: SQLiteConnection) {
            connection.execSQL(
                """
                CREATE TABLE IF NOT EXISTS cached_members (
                    id TEXT NOT NULL PRIMARY KEY,
                    memberNumber TEXT NOT NULL,
                    name TEXT NOT NULL
                )
                """,
            )
            connection.execSQL(
                """
                CREATE TABLE IF NOT EXISTS cached_sessions (
                    id TEXT NOT NULL PRIMARY KEY,
                    title TEXT NOT NULL,
                    location TEXT,
                    recordCount INTEGER NOT NULL
                )
                """,
            )
        }
    }

    @Provides
    fun providePendingCheckInDao(database: UnefyDatabase): PendingCheckInDao =
        database.pendingCheckInDao()

    @Provides
    fun provideCachedSessionDao(database: UnefyDatabase): CachedSessionDao =
        database.cachedSessionDao()

    @Provides
    fun provideCachedSessionRecordDao(database: UnefyDatabase): CachedSessionRecordDao =
        database.cachedSessionRecordDao()

    @Provides
    fun provideSyncedMemberDao(database: UnefyDatabase): SyncedMemberDao =
        database.syncedMemberDao()

    @Provides
    fun provideSyncCursorDao(database: UnefyDatabase): SyncCursorDao = database.syncCursorDao()

    /** The attendance list the scanner shows, so it survives losing signal. */
    private val MIGRATION_2_3 = object : Migration(2, 3) {
        override fun migrate(connection: SQLiteConnection) {
            connection.execSQL(
                """
                CREATE TABLE IF NOT EXISTS cached_session_records (
                    id TEXT NOT NULL PRIMARY KEY,
                    sessionId TEXT NOT NULL,
                    memberId TEXT NOT NULL,
                    memberName TEXT NOT NULL,
                    method TEXT NOT NULL,
                    checkedInAtEpochSeconds INTEGER NOT NULL
                )
                """,
            )
        }
    }

    /** Guests, who have no member id for a queued check-in to point at. */
    private val MIGRATION_3_4 = object : Migration(3, 4) {
        override fun migrate(connection: SQLiteConnection) {
            connection.execSQL("ALTER TABLE pending_check_ins ADD COLUMN guestName TEXT")
        }
    }

    /**
     * `memberId` becomes nullable, for guests.
     *
     * Dropped and recreated rather than rebuilt in place: SQLite cannot relax a
     * NOT NULL, and this table is a cache — it refills from the server on the
     * next load, so nothing is lost. The same shortcut would be indefensible
     * for `pending_check_ins`, which holds the only copy of what it stores.
     */
    private val MIGRATION_4_5 = object : Migration(4, 5) {
        override fun migrate(connection: SQLiteConnection) {
            connection.execSQL("DROP TABLE IF EXISTS cached_session_records")
            connection.execSQL(
                """
                CREATE TABLE cached_session_records (
                    id TEXT NOT NULL PRIMARY KEY,
                    sessionId TEXT NOT NULL,
                    memberId TEXT,
                    memberName TEXT NOT NULL,
                    method TEXT NOT NULL,
                    checkedInAtEpochSeconds INTEGER NOT NULL
                )
                """,
            )
        }
    }

    /**
     * The member mirror and the sync cursors.
     *
     * Purely additive — nothing existing is touched, so there is no data to
     * migrate. Both tables start empty and the first sync fills them: an empty
     * `sync_cursors` is exactly how a device says "bootstrap me".
     *
     * `searchKey`/`sortKey` are `NOT NULL` with no default because every row is
     * written through [SyncedMember], whose constructor derives them.
     */
    private val MIGRATION_5_6 = object : Migration(5, 6) {
        override fun migrate(connection: SQLiteConnection) {
            connection.execSQL(
                """
                CREATE TABLE IF NOT EXISTS synced_members (
                    id TEXT NOT NULL PRIMARY KEY,
                    memberNumber TEXT NOT NULL,
                    firstName TEXT NOT NULL,
                    lastName TEXT NOT NULL,
                    email TEXT,
                    phone TEXT,
                    mobile TEXT,
                    birthday TEXT,
                    street TEXT,
                    zipCode TEXT,
                    city TEXT,
                    status TEXT,
                    category TEXT,
                    joinedAt TEXT NOT NULL,
                    leftAt TEXT,
                    generation INTEGER NOT NULL,
                    searchKey TEXT NOT NULL,
                    sortKey TEXT NOT NULL
                )
                """,
            )
            // The list is always read in this order, and the search is a
            // substring match that no index can serve — so the index that pays
            // for itself is the one on the sort.
            connection.execSQL(
                "CREATE INDEX IF NOT EXISTS index_synced_members_sortKey ON synced_members (sortKey)",
            )
            connection.execSQL(
                """
                CREATE TABLE IF NOT EXISTS sync_cursors (
                    collection TEXT NOT NULL PRIMARY KEY,
                    cursor TEXT,
                    bootstrapComplete INTEGER NOT NULL,
                    generation INTEGER NOT NULL
                )
                """,
            )
        }
    }

    /**
     * The event, dues and competition mirrors.
     *
     * Purely additive, like 5→6: three empty tables the first sync fills. The
     * dues table joins against `synced_members` at read time, which is why it
     * indexes `memberId`; no foreign key, because the member row may arrive in
     * a later page of the same bootstrap.
     */
    private val MIGRATION_6_7 = object : Migration(6, 7) {
        override fun migrate(connection: SQLiteConnection) {
            connection.execSQL(
                """
                CREATE TABLE IF NOT EXISTS synced_events (
                    id TEXT NOT NULL PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    eventType TEXT,
                    location TEXT,
                    startsAt TEXT NOT NULL,
                    endsAt TEXT,
                    allDay INTEGER NOT NULL,
                    registrationRequired INTEGER NOT NULL,
                    registrationDeadline TEXT,
                    maxParticipants INTEGER,
                    status TEXT,
                    generation INTEGER NOT NULL
                )
                """,
            )
            connection.execSQL(
                "CREATE INDEX IF NOT EXISTS index_synced_events_startsAt " +
                    "ON synced_events (startsAt)",
            )
            connection.execSQL(
                """
                CREATE TABLE IF NOT EXISTS synced_dues (
                    id TEXT NOT NULL PRIMARY KEY,
                    memberId TEXT NOT NULL,
                    feeName TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    dueDate TEXT,
                    status TEXT,
                    paidAt TEXT,
                    generation INTEGER NOT NULL
                )
                """,
            )
            connection.execSQL(
                "CREATE INDEX IF NOT EXISTS index_synced_dues_dueDate ON synced_dues (dueDate)",
            )
            connection.execSQL(
                "CREATE INDEX IF NOT EXISTS index_synced_dues_memberId ON synced_dues (memberId)",
            )
            connection.execSQL(
                """
                CREATE TABLE IF NOT EXISTS synced_competitions (
                    id TEXT NOT NULL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    competitionType TEXT,
                    startDate TEXT NOT NULL,
                    endDate TEXT,
                    scoringUnit TEXT NOT NULL,
                    scoringMode TEXT NOT NULL,
                    disciplines TEXT NOT NULL,
                    generation INTEGER NOT NULL
                )
                """,
            )
            connection.execSQL(
                "CREATE INDEX IF NOT EXISTS index_synced_competitions_startDate " +
                    "ON synced_competitions (startDate)",
            )
        }
    }

    @Provides
    fun provideSyncedEventDao(database: UnefyDatabase): SyncedEventDao = database.syncedEventDao()

    @Provides
    fun provideSyncedDueDao(database: UnefyDatabase): SyncedDueDao = database.syncedDueDao()

    @Provides
    fun provideSyncedCompetitionDao(database: UnefyDatabase): SyncedCompetitionDao =
        database.syncedCompetitionDao()

    /**
     * The queue's client-assigned check-in id. Nullable on purpose: rows queued
     * before the column existed drain exactly as they always did, and every new
     * row gets its id at construction.
     */
    private val MIGRATION_7_8 = object : Migration(7, 8) {
        override fun migrate(connection: SQLiteConnection) {
            connection.execSQL("ALTER TABLE pending_check_ins ADD COLUMN clientId TEXT")
        }
    }

    /**
     * Drops `cached_members` — the manual check-in pick list reads the member
     * mirror now. Droppable precisely because it was a cache: nothing in it
     * existed only on the device, unlike the check-in queue.
     */
    private val MIGRATION_8_9 = object : Migration(8, 9) {
        override fun migrate(connection: SQLiteConnection) {
            connection.execSQL("DROP TABLE IF EXISTS cached_members")
        }
    }

    /**
     * The member's gender, newly carried by `MemberResponse`. Nullable TEXT:
     * existing rows stay NULL until the next sync page rewrites them.
     */
    private val MIGRATION_9_10 = object : Migration(9, 10) {
        override fun migrate(connection: SQLiteConnection) {
            connection.execSQL("ALTER TABLE synced_members ADD COLUMN gender TEXT")
        }
    }

    /**
     * Shot recording: the offline write queue and the member's own history.
     *
     * Purely additive. `pending_shot_entries` is a queue, not a cache — until a
     * series drains, this row is the only copy of it anywhere, which is the
     * reason this database still refuses a destructive fallback.
     */
    private val MIGRATION_10_11 = object : Migration(10, 11) {
        override fun migrate(connection: SQLiteConnection) {
            connection.execSQL(
                """
                CREATE TABLE IF NOT EXISTS pending_shot_entries (
                    id TEXT NOT NULL PRIMARY KEY,
                    memberId TEXT NOT NULL,
                    memberLabel TEXT,
                    sessionId TEXT,
                    occurredOn TEXT,
                    discipline TEXT,
                    targetType TEXT NOT NULL,
                    caliberMm REAL NOT NULL,
                    shotsJson TEXT NOT NULL,
                    localTotal INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    recordedAt TEXT NOT NULL,
                    notes TEXT,
                    attempts INTEGER NOT NULL,
                    lastError TEXT
                )
                """,
            )
            connection.execSQL(
                """
                CREATE TABLE IF NOT EXISTS cached_my_entries (
                    id TEXT NOT NULL PRIMARY KEY,
                    sessionId TEXT NOT NULL,
                    memberId TEXT NOT NULL,
                    scoreValue REAL NOT NULL,
                    scoreUnit TEXT NOT NULL,
                    discipline TEXT,
                    targetType TEXT,
                    caliberMm REAL,
                    shotsJson TEXT,
                    innerTens INTEGER,
                    groupingMm REAL,
                    source TEXT NOT NULL,
                    recordedAt TEXT NOT NULL,
                    notes TEXT
                )
                """,
            )
            connection.execSQL(
                "CREATE INDEX IF NOT EXISTS index_cached_my_entries_recordedAt " +
                    "ON cached_my_entries (recordedAt)",
            )
        }
    }

    @Provides
    fun providePendingShotEntryDao(database: UnefyDatabase): PendingShotEntryDao =
        database.pendingShotEntryDao()

    @Provides
    fun provideCachedShotEntryDao(database: UnefyDatabase): CachedShotEntryDao =
        database.cachedShotEntryDao()

    private const val DATABASE_NAME = "unefy.db"
}
