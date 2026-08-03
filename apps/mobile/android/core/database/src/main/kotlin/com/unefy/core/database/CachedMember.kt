package com.unefy.core.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Upsert

/**
 * Members, kept so the app can name them without a connection.
 *
 * Added for one concrete failure: the supervisor's manual check-in list came up
 * empty in a basement. Queueing the *write* was pointless while the *read* it
 * depends on stayed online-only — you cannot tick someone you cannot see.
 *
 * A cache, not a source of truth. It is refreshed on every successful load and
 * only consulted when the network refuses.
 */
@Entity(tableName = "cached_members")
data class CachedMember(
    @PrimaryKey val id: String,
    val memberNumber: String,
    val name: String,
)

@Dao
interface CachedMemberDao {

    /** Upsert rather than replace: a filtered search must not shrink the cache. */
    @Upsert
    suspend fun upsert(members: List<CachedMember>)

    @Query(
        """
        SELECT * FROM cached_members
        WHERE :query = '' OR name LIKE '%' || :query || '%' OR memberNumber LIKE '%' || :query || '%'
        ORDER BY name
        LIMIT :limit
        """,
    )
    suspend fun search(query: String, limit: Int): List<CachedMember>

    /**
     * After a full, unfiltered load, so members removed upstream do not linger.
     *
     * Empty split out: `NOT IN ()` is not valid SQL, and Room expands the list
     * literally — a club emptied upstream would have thrown rather than
     * cleared.
     */
    suspend fun retainOnly(keep: List<String>) {
        if (keep.isEmpty()) deleteAll() else retainOnlyOf(keep)
    }

    @Query("DELETE FROM cached_members WHERE id NOT IN (:keep)")
    suspend fun retainOnlyOf(keep: List<String>)

    @Query("DELETE FROM cached_members")
    suspend fun deleteAll()
}
