package com.unefy.core.database

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * The app's local database.
 *
 * Two tables, both earned rather than speculative: the check-in queue, and the
 * member list it needs to be usable offline. Caching for events and dues
 * belongs here too and is not built — see docs/plans/android-app.md.
 *
 * No `fallbackToDestructiveMigration`. The queue holds check-ins that exist
 * nowhere else until they sync, and dropping the table on a schema change would
 * silently lose an evening's attendance.
 */
@Database(
    entities = [PendingCheckIn::class, CachedMember::class],
    version = 1,
    exportSchema = true,
)
abstract class UnefyDatabase : RoomDatabase() {
    abstract fun pendingCheckInDao(): PendingCheckInDao

    abstract fun cachedMemberDao(): CachedMemberDao
}

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): UnefyDatabase =
        Room.databaseBuilder(context, UnefyDatabase::class.java, DATABASE_NAME).build()

    @Provides
    fun providePendingCheckInDao(database: UnefyDatabase): PendingCheckInDao =
        database.pendingCheckInDao()

    @Provides
    fun provideCachedMemberDao(database: UnefyDatabase): CachedMemberDao =
        database.cachedMemberDao()

    private const val DATABASE_NAME = "unefy.db"
}
