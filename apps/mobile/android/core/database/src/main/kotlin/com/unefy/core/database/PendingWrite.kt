package com.unefy.core.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Index
import androidx.room.Query
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

/**
 * A creation or an edit that has not reached the server yet.
 *
 * One table for every kind of record rather than one per feature: the queue's
 * job — hold it, retry it, show it as unsent, give up loudly — is the same
 * whatever is in [payloadJson], and [entity] is enough to hand the row back to
 * the feature that understands it. `PendingShotEntry` stayed typed because a
 * series is a shape nothing else has; a member and an event differ only in
 * their fields.
 *
 * **The primary key is (entity, recordId), not a queue id.** That is the
 * invariant the rest of the design leans on: a record can have at most one
 * unsent write. Editing something that is still queued rewrites that row
 * instead of stacking a second one behind it, so the queue can never contain
 * two versions of the same record in an order that matters.
 *
 * [tenantId] is not decoration. A queued write survives sign-out — it is the
 * only copy, exactly like a queued check-in — and draining it under whoever
 * signs in next would file it in *their* club. So the drain skips rows stamped
 * with another club's id, and they wait for the account that made them.
 */
@Entity(
    tableName = "pending_writes",
    primaryKeys = ["entity", "recordId"],
    indices = [Index("tenantId"), Index("queuedAt")],
)
data class PendingWrite(
    /** `"members"`, `"events"` — the same names the sync collections use. */
    val entity: String,
    /**
     * The record's own id. For a creation the device picks it and the server
     * accepts it, which is what makes a retry safe and lets the app show and
     * open the record before it has ever been sent.
     */
    val recordId: String,
    /** [OP_CREATE] or [OP_UPDATE]. */
    val op: String,
    /** Which club this was written for. See the note on the class. */
    val tenantId: String,
    /** The request body, exactly as it will be sent. */
    val payloadJson: String,
    /** What to call this row in a list while it is still queued. */
    val label: String,
    /** Device clock, ISO-8601. Drains oldest first. */
    val queuedAt: String,
    /**
     * Kept so a row the server keeps refusing can be shown to somebody instead
     * of being retried forever in silence.
     */
    val attempts: Int = 0,
    val lastError: String? = null,
) {
    companion object {
        const val OP_CREATE = "create"
        const val OP_UPDATE = "update"
    }
}

@Dao
interface PendingWriteDao {

    /**
     * Insert or overwrite. Overwriting is the point: a second edit of the same
     * record replaces the first, because the form always submits every field it
     * owns, so the newer payload is a complete replacement rather than
     * something that would have to be merged onto the older one.
     */
    @Upsert
    suspend fun upsert(write: PendingWrite)

    @Query("SELECT * FROM pending_writes WHERE entity = :entity ORDER BY queuedAt ASC")
    fun stream(entity: String): Flow<List<PendingWrite>>

    @Query(
        "SELECT * FROM pending_writes WHERE entity = :entity AND recordId = :recordId",
    )
    suspend fun byId(entity: String, recordId: String): PendingWrite?

    @Query(
        "SELECT * FROM pending_writes WHERE entity = :entity AND recordId = :recordId",
    )
    fun byIdStream(entity: String, recordId: String): Flow<PendingWrite?>

    /** Oldest first, and only this club's — see the note on [PendingWrite]. */
    @Query("SELECT * FROM pending_writes WHERE tenantId = :tenantId ORDER BY queuedAt ASC")
    suspend fun drainable(tenantId: String): List<PendingWrite>

    @Query("SELECT COUNT(*) FROM pending_writes WHERE tenantId = :tenantId")
    fun countStream(tenantId: String): Flow<Int>

    @Query("DELETE FROM pending_writes WHERE entity = :entity AND recordId = :recordId")
    suspend fun delete(entity: String, recordId: String)

    @Query(
        "UPDATE pending_writes SET attempts = attempts + 1, lastError = :error " +
            "WHERE entity = :entity AND recordId = :recordId",
    )
    suspend fun recordFailure(entity: String, recordId: String, error: String?)

    @Query("DELETE FROM pending_writes")
    suspend fun deleteAll()
}
