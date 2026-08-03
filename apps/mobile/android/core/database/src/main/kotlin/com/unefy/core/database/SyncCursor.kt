package com.unefy.core.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

/**
 * How far this device has read one collection's change feed.
 *
 * The cursor is an opaque token the server produced — base64 of a
 * `(updated_at, id)` pair, see backend/app/sync/cursor.py. The device never reads
 * it, computes with it or compares it; it stores a blob and hands it back. That
 * is what rules out clock skew structurally instead of tolerating it.
 *
 * **In Room, not DataStore, and that is the point.** The cursor has to advance in
 * the same transaction that writes the rows it accounts for. Split apart, a crash
 * between the two leaves the cursor past rows that were never stored — a hole
 * that no later sync can see, because the server will not send them again. Same
 * invariant as the server's "the delivered set is a superset of the changed set,
 * never a subset", just from this end.
 */
@Entity(tableName = "sync_cursors")
data class SyncCursorEntity(
    @PrimaryKey val collection: String,
    /** Null until the first page lands. Absent row and null both mean "bootstrap". */
    val cursor: String?,
    /**
     * The cold start has drained to the end. Until then the mirror is a partial
     * list a screen must not present as the club, and [SyncedMemberDao.sweep]
     * must not run.
     */
    val bootstrapComplete: Boolean,
    /** Stamped onto every row this sync writes. See [SyncedMemberDao.sweep]. */
    val generation: Long,
)

@Dao
interface SyncCursorDao {

    @Query("SELECT * FROM sync_cursors WHERE collection = :collection")
    suspend fun get(collection: String): SyncCursorEntity?

    /**
     * Whether this collection's cold start has drained to the end.
     *
     * The screens need it to tell "still bootstrapping" from "this club really
     * has no members" — without it, a first launch shows an empty state instead
     * of a skeleton. The flag, not mere row existence: the cursor row is written
     * after every page, so a row exists the moment page one of ten lands, and a
     * screen keying on existence would present a fifth of the club as all of it
     * — the header would say 200 for a club of 1000 and a search for anyone in
     * the other four fifths would silently find nothing.
     */
    @Query(
        "SELECT COALESCE(" +
            "(SELECT bootstrapComplete FROM sync_cursors WHERE collection = :collection), 0)",
    )
    fun bootstrapCompleteStream(collection: String): Flow<Boolean>

    @Upsert
    suspend fun upsert(cursor: SyncCursorEntity)

    @Query("DELETE FROM sync_cursors")
    suspend fun deleteAll()
}
