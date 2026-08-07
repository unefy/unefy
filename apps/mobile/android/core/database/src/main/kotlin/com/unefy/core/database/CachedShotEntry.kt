package com.unefy.core.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

/**
 * The member's own recorded series, as last seen from the server.
 *
 * A *cache*, not a mirror: filled from `GET /api/v1/entries/me` on refresh, not
 * by delta-sync. Entries are board-only in the sync registry, and widening that
 * would put every member's scores on every device; a self-scoped sync collection
 * is the better answer but a much larger change — see the V2 list in the plan.
 *
 * Being a cache is what makes it droppable in a future migration, unlike
 * [PendingShotEntry], which holds the only copy of anything it contains.
 */
@Entity(
    tableName = "cached_my_entries",
    indices = [Index("recordedAt")],
)
data class CachedShotEntry(
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
)

@Dao
interface CachedShotEntryDao {

    /** Newest first: the shooter wants today's series, not their first ever. */
    @Query("SELECT * FROM cached_my_entries ORDER BY recordedAt DESC")
    fun all(): Flow<List<CachedShotEntry>>

    @Query("SELECT * FROM cached_my_entries WHERE id = :id")
    fun byIdStream(id: String): Flow<CachedShotEntry?>

    @Upsert
    suspend fun upsert(entries: List<CachedShotEntry>)

    /**
     * Replace the cache with what the server just returned.
     *
     * A wholesale swap rather than an upsert because this is a cache of one
     * query's result: a series deleted on the server has to disappear here too,
     * and without a delta feed there is nothing else that would remove it.
     */
    @androidx.room.Transaction
    suspend fun replaceAll(entries: List<CachedShotEntry>) {
        deleteAll()
        upsert(entries)
    }

    @Query("DELETE FROM cached_my_entries WHERE id = :id")
    suspend fun deleteById(id: String)

    @Query("DELETE FROM cached_my_entries")
    suspend fun deleteAll()
}
