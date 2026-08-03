package com.unefy.core.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Upsert

/**
 * Who is already checked in, per session.
 *
 * Cached for the same reason as the member list: the supervisor's whole job is
 * knowing who is in the room, and a screen that can only say "someone was just
 * scanned" is a worse tool than the paper list it replaces. Offline that
 * question still has an answer — the one from the last time there was signal,
 * plus whatever this device has buffered since.
 */
@Entity(tableName = "cached_session_records")
data class CachedSessionRecord(
    @PrimaryKey val id: String,
    val sessionId: String,
    /** Null for a guest; `memberName` carries their name either way. */
    val memberId: String?,
    val memberName: String,
    val method: String,
    /** Unix seconds, so ordering does not depend on parsing a string. */
    val checkedInAtEpochSeconds: Long,
)

@Dao
interface CachedSessionRecordDao {

    @Upsert
    suspend fun upsert(records: List<CachedSessionRecord>)

    /** Newest first: the person just checked in is the one being looked at. */
    @Query(
        "SELECT * FROM cached_session_records WHERE sessionId = :sessionId " +
            "ORDER BY checkedInAtEpochSeconds DESC",
    )
    suspend fun forSession(sessionId: String): List<CachedSessionRecord>

    /**
     * After a successful load, so records corrected away upstream disappear.
     *
     * The empty case is split out because `NOT IN ()` is not valid SQL — Room
     * expands the list literally, and an empty one made this throw instead of
     * clearing. The visible effect was a session emptied on the server still
     * showing its old attendance on the phone, which is the one direction a
     * cache must never fail in.
     */
    suspend fun retainOnly(sessionId: String, keep: List<String>) {
        if (keep.isEmpty()) deleteForSession(sessionId) else retainOnlyOf(sessionId, keep)
    }

    @Query("DELETE FROM cached_session_records WHERE sessionId = :sessionId AND id NOT IN (:keep)")
    suspend fun retainOnlyOf(sessionId: String, keep: List<String>)

    @Query("DELETE FROM cached_session_records WHERE sessionId = :sessionId")
    suspend fun deleteForSession(sessionId: String)
}
