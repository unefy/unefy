package com.unefy.core.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

/**
 * The mirror of the club's events — the source the events screen reads from.
 *
 * Filled by delta-sync (`GET /api/v1/sync/events`) and emptied only by sign-out.
 *
 * **No caller-specific or derived fields.** The sync payload is the bare row:
 * `is_registered` does not exist there at all, and `registered_count` /
 * `competition_name` arrive as their defaults. Those three come from an online
 * overlay over `GET /api/v1/events` instead — mirroring their defaults would
 * present every event as "not registered, 0 participants" and make the lie
 * permanent offline. `competition_id`/`session_id` are omitted because no
 * screen reads them.
 */
@Entity(
    tableName = "synced_events",
    // The list is always read in start order; that is the sort worth indexing.
    indices = [Index("startsAt")],
)
data class SyncedEvent(
    @PrimaryKey val id: String,
    val title: String,
    val description: String?,
    val eventType: String?,
    val location: String?,
    /** ISO-8601 UTC instant — lexicographic order is chronological order. */
    val startsAt: String,
    val endsAt: String?,
    val allDay: Boolean,
    val registrationRequired: Boolean,
    val registrationDeadline: String?,
    val maxParticipants: Int?,
    val status: String?,
    /** Which bootstrap wrote this row. See [SyncedMemberDao.sweep]. */
    val generation: Long,
)

@Dao
interface SyncedEventDao {

    /** Ascending by start; the ViewModel splits upcoming/past locally. */
    @Query("SELECT * FROM synced_events ORDER BY startsAt, title")
    fun all(): Flow<List<SyncedEvent>>

    @Upsert
    suspend fun upsert(events: List<SyncedEvent>)

    /** Tombstones. `IN ()` is not valid SQL, so an empty page must not reach it. */
    suspend fun deleteByIds(ids: List<String>) {
        if (ids.isNotEmpty()) deleteByIdsOf(ids)
    }

    @Query("DELETE FROM synced_events WHERE id IN (:ids)")
    suspend fun deleteByIdsOf(ids: List<String>)

    /** Drops rows a re-bootstrap did not touch. See [SyncedMemberDao.sweep]. */
    @Query("DELETE FROM synced_events WHERE generation < :generation")
    suspend fun sweep(generation: Long)

    @Query("DELETE FROM synced_events")
    suspend fun deleteAll()
}
