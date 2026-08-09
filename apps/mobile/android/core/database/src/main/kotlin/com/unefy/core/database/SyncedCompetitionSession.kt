package com.unefy.core.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

/**
 * The mirror of a competition's rounds — match days, legs, training evenings.
 *
 * Filled by delta-sync (`GET /api/v1/sync/competition-sessions`), visible to
 * every role. Mirrored rather than fetched live for the same reason as the
 * check-in seed: the round is picked at the range, and ranges are basements.
 * Without it a series filed from the app can only land in "Freies Training".
 */
@Entity(
    tableName = "synced_competition_sessions",
    indices = [Index("competitionId"), Index("date")],
)
data class SyncedCompetitionSession(
    @PrimaryKey val id: String,
    val competitionId: String,
    val name: String?,
    /** ISO date — lexicographic order is chronological order. */
    val date: String,
    val location: String?,
    val discipline: String?,
    /** Set when the round also sits in the calendar as an event. */
    val eventId: String?,
    /** Which bootstrap wrote this row. See [SyncedMemberDao.sweep]. */
    val generation: Long,
)

@Dao
interface SyncedCompetitionSessionDao {

    /** The rounds of one competition, newest first. */
    @Query(
        "SELECT * FROM synced_competition_sessions WHERE competitionId = :competitionId " +
            "ORDER BY date DESC",
    )
    fun byCompetition(competitionId: String): Flow<List<SyncedCompetitionSession>>

    /** One round, for the screen that records into it. */
    @Query("SELECT * FROM synced_competition_sessions WHERE id = :id")
    suspend fun byId(id: String): SyncedCompetitionSession?

    @Upsert
    suspend fun upsert(sessions: List<SyncedCompetitionSession>)

    /** Tombstones. `IN ()` is not valid SQL, so an empty page must not reach it. */
    suspend fun deleteByIds(ids: List<String>) {
        if (ids.isNotEmpty()) deleteByIdsOf(ids)
    }

    @Query("DELETE FROM synced_competition_sessions WHERE id IN (:ids)")
    suspend fun deleteByIdsOf(ids: List<String>)

    /** Drops rows a re-bootstrap did not touch. See [SyncedMemberDao.sweep]. */
    @Query("DELETE FROM synced_competition_sessions WHERE generation < :generation")
    suspend fun sweep(generation: Long)

    @Query("DELETE FROM synced_competition_sessions")
    suspend fun deleteAll()
}
