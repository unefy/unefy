package com.unefy.core.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

/**
 * The mirror of the *club's* recorded series — every member's, not just the
 * caller's. Filled by delta-sync (`GET /api/v1/sync/entries`), emptied only by
 * sign-out.
 *
 * Board-only, and that is enforced on the server: the `entries` collection sits
 * in the registry's default role set, so a plain member's sync request is
 * refused and this table simply stays empty on their device. Nothing here may
 * be shown without checking [com.unefy.core.model.ClubRole.canAdminister] as
 * well — a device that was board yesterday still holds the rows today.
 *
 * Distinct from [CachedShotEntry], which holds the caller's own history and is
 * filled from `GET /api/v1/entries/me`. The two overlap for a board member's own
 * series, deliberately: the personal list has to work offline for everyone, and
 * it cannot depend on a mirror that most accounts never receive.
 */
@Entity(
    tableName = "synced_entries",
    indices = [Index("recordedAt"), Index("memberId")],
)
data class SyncedEntry(
    @PrimaryKey val id: String,
    val sessionId: String,
    val memberId: String,
    val scoreValue: Double,
    val scoreUnit: String,
    val discipline: String?,
    val targetType: String?,
    val caliberMm: Double?,
    /** `[{"x":…,"y":…,"ring":…}]`, verbatim from `details.shots`. */
    val shotsJson: String?,
    val innerTens: Int?,
    val groupingMm: Double?,
    val source: String,
    /** ISO-8601 — lexicographic order is chronological order. */
    val recordedAt: String,
    val notes: String?,
    /** Which bootstrap wrote this row. See [SyncedMemberDao.sweep]. */
    val generation: Long,
)

@Dao
interface SyncedEntryDao {

    /** Newest first — a club looks at this evening, not at last season. */
    @Query("SELECT * FROM synced_entries ORDER BY recordedAt DESC")
    fun all(): Flow<List<SyncedEntry>>

    @Query("SELECT * FROM synced_entries WHERE memberId = :memberId ORDER BY recordedAt DESC")
    fun byMember(memberId: String): Flow<List<SyncedEntry>>

    /**
     * One row, once. Used when a correction has to be written straight into the
     * mirror: the new values are known, but the row's [SyncedEntry.generation]
     * must be carried over or the next bootstrap's sweep would drop it.
     */
    @Query("SELECT * FROM synced_entries WHERE id = :id")
    suspend fun byId(id: String): SyncedEntry?

    @Upsert
    suspend fun upsert(entries: List<SyncedEntry>)

    @Query("DELETE FROM synced_entries WHERE id IN (:ids)")
    suspend fun deleteByIds(ids: List<String>)

    /**
     * Drop rows an older bootstrap left behind. See [SyncedMemberDao.sweep] for
     * why the generation counter exists rather than a clear-then-fill.
     */
    @Query("DELETE FROM synced_entries WHERE generation < :generation")
    suspend fun sweep(generation: Long)

    @Query("DELETE FROM synced_entries")
    suspend fun deleteAll()
}
