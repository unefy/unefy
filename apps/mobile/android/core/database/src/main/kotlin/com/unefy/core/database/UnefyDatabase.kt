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
 * Three tables, all earned rather than speculative: the check-in queue, and the
 * member and session lists it needs to be usable offline. Caching for events
 * and dues belongs here too and is not built — see docs/plans/android-app.md.
 *
 * No `fallbackToDestructiveMigration`. The queue holds check-ins that exist
 * nowhere else until they sync, and dropping the table on a schema change would
 * silently lose an evening's attendance.
 */
@Database(
    entities = [PendingCheckIn::class, CachedMember::class, CachedSession::class],
    version = 2,
    exportSchema = true,
)
abstract class UnefyDatabase : RoomDatabase() {
    abstract fun pendingCheckInDao(): PendingCheckInDao

    abstract fun cachedMemberDao(): CachedMemberDao

    abstract fun cachedSessionDao(): CachedSessionDao
}

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): UnefyDatabase =
        Room.databaseBuilder(context, UnefyDatabase::class.java, DATABASE_NAME)
            .addMigrations(MIGRATION_1_2)
            .build()

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
    fun provideCachedMemberDao(database: UnefyDatabase): CachedMemberDao =
        database.cachedMemberDao()

    @Provides
    fun provideCachedSessionDao(database: UnefyDatabase): CachedSessionDao =
        database.cachedSessionDao()

    private const val DATABASE_NAME = "unefy.db"
}
