package com.unefy.core.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Upsert

/**
 * Open attendance sessions, kept so the scanner has something to check into
 * without a connection.
 *
 * The last piece of the offline path: a supervisor who opens the scanner in the
 * basement, having last used it upstairs, would otherwise see no session — and
 * with no session the queue never gets a chance to hold anything, because there
 * is nothing to buffer *into*.
 *
 * Only open sessions are stored. A closed one cannot take a check-in, so
 * offering it offline would only produce a refusal on sync.
 */
@Entity(tableName = "cached_sessions")
data class CachedSession(
    @PrimaryKey val id: String,
    val title: String,
    val location: String?,
    val recordCount: Int,
)

@Dao
interface CachedSessionDao {

    @Upsert
    suspend fun upsert(sessions: List<CachedSession>)

    @Query("SELECT * FROM cached_sessions ORDER BY title")
    suspend fun all(): List<CachedSession>

    /**
     * After a successful load, so sessions closed upstream stop being offered.
     *
     * Empty split out for the same reason as the others: closing the last
     * session is exactly when this has to work, and `NOT IN ()` would have
     * thrown instead.
     */
    suspend fun retainOnly(keep: List<String>) {
        if (keep.isEmpty()) deleteAll() else retainOnlyOf(keep)
    }

    @Query("DELETE FROM cached_sessions WHERE id NOT IN (:keep)")
    suspend fun retainOnlyOf(keep: List<String>)

    @Query("DELETE FROM cached_sessions")
    suspend fun deleteAll()
}
