package com.unefy.core.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.PrimaryKey
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

/**
 * A check-in taken while the device could not reach the server.
 *
 * The reason this table exists: shooting ranges are in basements, and a
 * supervisor scanning a queue there would otherwise lose every check-in the
 * moment the signal drops. What is stored is the *claim* — who, into which
 * session, and when by this device's clock — because by the time it is sent the
 * server's clock says something else entirely. The backend keeps the two apart
 * as `checked_in_at` and `synced_at`.
 *
 * All three ways in share one row: `code` for a scan, `memberId` for a manual
 * tick, `guestName` for somebody who is not a member. Which one is set decides
 * what the sync sends.
 */
@Entity(tableName = "pending_check_ins")
data class PendingCheckIn(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val sessionId: String,
    /** Set for a scanned code; null for a manual tick. */
    val code: String? = null,
    /** Set for a manual tick; null for a scan, where the code names the member. */
    val memberId: String? = null,
    /** Set for a guest, who has no member record to point at. */
    val guestName: String? = null,
    /** For showing the supervisor what is still queued, without a lookup. */
    val memberLabel: String? = null,
    /** Device clock, unix seconds. The only record of when this happened. */
    val checkedInAtEpochSeconds: Long,
    val installId: String? = null,
    /**
     * How often sending has been tried. Kept so a row that the server keeps
     * refusing can be surfaced rather than retried forever in silence.
     */
    val attempts: Int = 0,
    /** The last refusal, for the same reason. */
    val lastError: String? = null,
)

@Dao
interface PendingCheckInDao {

    @Insert
    suspend fun insert(entry: PendingCheckIn): Long

    /** Oldest first: the queue drains in the order the people arrived. */
    @Query("SELECT * FROM pending_check_ins ORDER BY checkedInAtEpochSeconds ASC")
    suspend fun all(): List<PendingCheckIn>

    @Query("SELECT COUNT(*) FROM pending_check_ins")
    fun countStream(): Flow<Int>

    @Query("SELECT * FROM pending_check_ins WHERE sessionId = :sessionId")
    suspend fun forSession(sessionId: String): List<PendingCheckIn>

    @Query("DELETE FROM pending_check_ins WHERE id = :id")
    suspend fun delete(id: Long)

    @Query("UPDATE pending_check_ins SET attempts = attempts + 1, lastError = :error WHERE id = :id")
    suspend fun recordFailure(id: Long, error: String?)
}
