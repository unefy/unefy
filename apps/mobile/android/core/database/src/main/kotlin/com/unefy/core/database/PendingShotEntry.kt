package com.unefy.core.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Update
import java.util.UUID
import kotlinx.coroutines.flow.Flow

/**
 * A recorded series of shots that has not reached the server yet.
 *
 * Ranges have no signal, so this is the normal path rather than the exception:
 * a series is written here first and sent whenever the network comes back. Until
 * then this row is the only copy — which is why the database has no destructive
 * migration fallback.
 *
 * The shots themselves live in [shotsJson] rather than a child table. They are
 * only ever read and written as one set, the whole series is a single request,
 * and the project has no Room type converters — `SyncedCompetition` joins its
 * discipline list into one column for the same reason.
 */
@Entity(tableName = "pending_shot_entries")
data class PendingShotEntry(
    /**
     * Client-generated, and sent as the entry's `id`. The server treats a replay
     * of this key as the same entry, so a drain interrupted halfway does not
     * turn one series into two.
     */
    @PrimaryKey val id: String = UUID.randomUUID().toString(),
    val memberId: String,
    /** For showing who it belongs to while it is still queued, without a join. */
    val memberLabel: String? = null,
    /** Set when filing under a competition; null means free training. */
    val sessionId: String? = null,
    /** The day the series was shot. Required when [sessionId] is null. */
    val occurredOn: String? = null,
    val discipline: String? = null,
    val targetType: String,
    val caliberMm: Double,
    /** `[{"x":…,"y":…,"caliberMm":…,"ring":…}]` — see `ShotEntryPayload`. */
    val shotsJson: String,
    /** Total as scored on the device. The server recomputes it; this is for the UI. */
    val localTotal: Int,
    val source: String = "manual",
    /** Device clock, ISO-8601. The only record of when this actually happened. */
    val recordedAt: String,
    val notes: String? = null,
    /**
     * Kept so a row the server keeps refusing can be surfaced instead of being
     * retried forever in silence.
     */
    val attempts: Int = 0,
    val lastError: String? = null,
)

@Dao
interface PendingShotEntryDao {

    @Insert
    suspend fun insert(entry: PendingShotEntry)

    @Update
    suspend fun update(entry: PendingShotEntry)

    /** Oldest first, so a day's shooting syncs in the order it happened. */
    @Query("SELECT * FROM pending_shot_entries ORDER BY recordedAt ASC")
    suspend fun all(): List<PendingShotEntry>

    @Query("SELECT * FROM pending_shot_entries ORDER BY recordedAt DESC")
    fun stream(): Flow<List<PendingShotEntry>>

    @Query("SELECT * FROM pending_shot_entries WHERE memberId = :memberId ORDER BY recordedAt DESC")
    fun streamForMember(memberId: String): Flow<List<PendingShotEntry>>

    @Query("SELECT * FROM pending_shot_entries WHERE id = :id")
    suspend fun byId(id: String): PendingShotEntry?

    @Query("SELECT COUNT(*) FROM pending_shot_entries")
    fun countStream(): Flow<Int>

    @Query("DELETE FROM pending_shot_entries WHERE id = :id")
    suspend fun delete(id: String)

    @Query(
        "UPDATE pending_shot_entries SET attempts = attempts + 1, lastError = :error " +
            "WHERE id = :id",
    )
    suspend fun recordFailure(id: String, error: String?)

    @Query("DELETE FROM pending_shot_entries")
    suspend fun deleteAll()
}
