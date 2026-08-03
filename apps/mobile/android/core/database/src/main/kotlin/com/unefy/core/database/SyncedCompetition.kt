package com.unefy.core.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

/**
 * Joins the `disciplines` list into one column and back. A control character
 * rather than a comma because discipline names are free text; U+001F is the
 * ASCII unit separator, which is exactly this job. No TypeConverter — this
 * module stays free of serialization, and both directions live next to the
 * entity so they cannot drift.
 */
const val DISCIPLINES_SEPARATOR = "\u001F"

/**
 * The mirror of the club's competitions — the source the competitions list
 * reads from. Filled by delta-sync (`GET /api/v1/sync/competitions`), visible
 * to every role, emptied only by sign-out.
 *
 * The scoreboard is deliberately not mirrored: it is a server-side aggregate
 * with its own endpoint, and a stale ranking shown as current would be worse
 * than a spinner.
 */
@Entity(
    tableName = "synced_competitions",
    indices = [Index("startDate")],
)
data class SyncedCompetition(
    @PrimaryKey val id: String,
    val name: String,
    val description: String?,
    val competitionType: String?,
    /** ISO date — lexicographic order is chronological order. */
    val startDate: String,
    val endDate: String?,
    val scoringUnit: String,
    val scoringMode: String,
    /** Joined with [DISCIPLINES_SEPARATOR]; empty string means none. */
    val disciplines: String,
    /** Which bootstrap wrote this row. See [SyncedMemberDao.sweep]. */
    val generation: Long,
)

@Dao
interface SyncedCompetitionDao {

    /** Newest first — the order the screen has always shown. */
    @Query("SELECT * FROM synced_competitions ORDER BY startDate DESC, name")
    fun all(): Flow<List<SyncedCompetition>>

    /** One competition, live: the detail updates when a sync touches the row. */
    @Query("SELECT * FROM synced_competitions WHERE id = :id")
    fun byIdStream(id: String): Flow<SyncedCompetition?>

    @Upsert
    suspend fun upsert(competitions: List<SyncedCompetition>)

    /** Tombstones. `IN ()` is not valid SQL, so an empty page must not reach it. */
    suspend fun deleteByIds(ids: List<String>) {
        if (ids.isNotEmpty()) deleteByIdsOf(ids)
    }

    @Query("DELETE FROM synced_competitions WHERE id IN (:ids)")
    suspend fun deleteByIdsOf(ids: List<String>)

    /** Drops rows a re-bootstrap did not touch. See [SyncedMemberDao.sweep]. */
    @Query("DELETE FROM synced_competitions WHERE generation < :generation")
    suspend fun sweep(generation: Long)

    @Query("DELETE FROM synced_competitions")
    suspend fun deleteAll()
}
