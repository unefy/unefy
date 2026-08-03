package com.unefy.core.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

/**
 * The mirror of the club's dues ledger — board-only, like the sync collection
 * that fills it (`GET /api/v1/sync/dues` answers 403 for a plain member, and the
 * coordinator latches that as NotPermitted).
 *
 * **What sits on the device, argued rather than assumed:** amounts and payment
 * status per member, on a board member's private phone. That is the same class
 * of data as the member mirror it joins against (addresses, birthdays), gated
 * to the same roles. The payload carries **no** IBAN/SEPA fields — those exist
 * only on `MemberResponse` and are already excluded from [SyncedMember].
 * `payment_method` and `note` are deliberately not mirrored: no screen reads
 * them, and the mirror follows the DTO-subset principle.
 *
 * **No `memberName` column.** The sync payload's `member_name` is always null
 * (it is list-endpoint enrichment); the name comes from a local join against
 * [SyncedMember] instead, so a rename arrives via the member mirror without the
 * dues rows going stale.
 */
@Entity(
    tableName = "synced_dues",
    indices = [Index("dueDate"), Index("memberId")],
)
data class SyncedDue(
    @PrimaryKey val id: String,
    val memberId: String,
    val feeName: String,
    /** Decimal string, never a float — the convention from core:model/Dues.kt. */
    val amount: String,
    val dueDate: String?,
    val status: String?,
    val paidAt: String?,
    /** Which bootstrap wrote this row. See [SyncedMemberDao.sweep]. */
    val generation: Long,
)

/**
 * A dues row with the member's name joined in. A Room projection, not an
 * entity — the name lives in `synced_members` and is joined at read time.
 */
data class DueWithMemberName(
    val id: String,
    val memberId: String,
    val feeName: String,
    val amount: String,
    val dueDate: String?,
    val status: String?,
    val paidAt: String?,
    val memberName: String,
)

@Dao
interface SyncedDueDao {

    /**
     * The ledger, newest due date first, with the member name joined from the
     * mirror. The status filter runs in SQL — it is the local replacement for
     * the server-side filter the chips used to reload with.
     *
     * `memberName` can be `""` for a moment while the member bootstrap is still
     * draining (both collections drain in the same pass); the flow re-emits as
     * soon as the member rows land, so no special case is needed.
     */
    @Query(
        """
        SELECT d.id, d.memberId, d.feeName, d.amount, d.dueDate, d.status, d.paidAt,
               COALESCE(m.firstName || ' ' || m.lastName, '') AS memberName
        FROM synced_dues d
        LEFT JOIN synced_members m ON m.id = d.memberId
        WHERE :status IS NULL OR d.status = :status
        ORDER BY (d.dueDate IS NULL), d.dueDate DESC, memberName
        """,
    )
    fun withMemberNames(status: String?): Flow<List<DueWithMemberName>>

    @Upsert
    suspend fun upsert(dues: List<SyncedDue>)

    /** Tombstones. `IN ()` is not valid SQL, so an empty page must not reach it. */
    suspend fun deleteByIds(ids: List<String>) {
        if (ids.isNotEmpty()) deleteByIdsOf(ids)
    }

    @Query("DELETE FROM synced_dues WHERE id IN (:ids)")
    suspend fun deleteByIdsOf(ids: List<String>)

    /** Drops rows a re-bootstrap did not touch. See [SyncedMemberDao.sweep]. */
    @Query("DELETE FROM synced_dues WHERE generation < :generation")
    suspend fun sweep(generation: Long)

    @Query("DELETE FROM synced_dues")
    suspend fun deleteAll()
}
