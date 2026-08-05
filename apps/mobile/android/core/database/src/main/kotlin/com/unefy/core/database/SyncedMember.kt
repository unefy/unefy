package com.unefy.core.database

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Upsert
import java.util.Locale
import kotlinx.coroutines.flow.Flow

/**
 * The mirror of the club's member list — the source the member screens read from,
 * not a cache they fall back to.
 *
 * Filled by delta-sync (`GET /api/v1/sync/members`) and emptied only by sign-out.
 * That is the difference from the attendance caches (sessions, records), which
 * are refreshed from whatever a list call happened to return and are consulted
 * only when the network refuses.
 *
 * **No banking fields.** `MemberResponse` carries `iban`, `bic` and
 * `sepa_mandate_reference`, and mirroring them would put every member's bank
 * details in plain text in this file, on a board member's private phone. The
 * backend already makes this distinction twice — `MemberDirectoryEntry` exists to
 * narrow exactly these fields away, and a tombstone deliberately carries no row
 * body. The detail screen fetches them per member when it is online; offline the
 * line stays empty rather than wrong.
 */
@Entity(
    tableName = "synced_members",
    // The list is always read in this order; the search is a substring match no
    // index can serve, so the sort is the part worth indexing.
    indices = [Index("sortKey")],
)
data class SyncedMember(
    @PrimaryKey val id: String,
    val memberNumber: String,
    val firstName: String,
    val lastName: String,
    val email: String?,
    val phone: String?,
    val mobile: String?,
    val birthday: String?,
    val gender: String?,
    val street: String?,
    val zipCode: String?,
    val city: String?,
    val status: String?,
    val category: String?,
    val joinedAt: String,
    val leftAt: String?,
    /**
     * Which bootstrap wrote this row. A re-bootstrap (after `409
     * CURSOR_TOO_OLD`) stamps every row it sees with a new value, and rows left
     * behind are the ones that were hard-deleted upstream — deletions no
     * tombstone can ever report. See [SyncedMemberDao.sweep].
     */
    val generation: Long,
    /**
     * Defaulted from the other fields so a row cannot be written with a stale
     * key. Room passes the stored values when it hydrates a row, so the default
     * only ever runs where the row is actually built.
     */
    val searchKey: String = foldForSearch(
        listOfNotNull(firstName, lastName, memberNumber, email).joinToString(" "),
    ),
    val sortKey: String = foldForSearch("$lastName $firstName"),
)

/**
 * Lower-cases and strips German diacritics, for both stored keys and the queries
 * run against them.
 *
 * SQLite's `LIKE` and `COLLATE NOCASE` fold ASCII only: without this, "über"
 * would not match "Über", and `ORDER BY` would sort "Ähnlich" after
 * "Zimmermann". Folding umlauts to their base letter is also what DIN 5007-1
 * prescribes for sorting, and it makes the search forgiving in the direction
 * people actually type — "mueller", "muller" and "müller" all find Müller.
 *
 * `lowercase()` without a locale would be wrong on a Turkish device, where `I`
 * lower-cases to a dotless ı.
 */
fun foldForSearch(text: String): String = text
    .lowercase(Locale.GERMAN)
    .replace("ä", "a")
    .replace("ö", "o")
    .replace("ü", "u")
    .replace("ß", "ss")

@Dao
interface SyncedMemberDao {

    /**
     * The list a screen shows. Folds the query the same way the stored key was
     * folded — a default method rather than a second call site, because the two
     * only work as a pair and a caller passing a raw query would silently find
     * nothing with an umlaut in it.
     */
    fun search(query: String): Flow<List<SyncedMember>> = searchFolded(foldForSearch(query))

    @Query(
        """
        SELECT * FROM synced_members
        WHERE :query = '' OR searchKey LIKE '%' || :query || '%'
        ORDER BY sortKey
        """,
    )
    fun searchFolded(query: String): Flow<List<SyncedMember>>

    /** How many the club has. After a completed sync that is the whole club. */
    @Query("SELECT COUNT(*) FROM synced_members")
    fun countStream(): Flow<Int>

    @Query("SELECT * FROM synced_members WHERE id = :id")
    fun byIdStream(id: String): Flow<SyncedMember?>

    @Upsert
    suspend fun upsert(members: List<SyncedMember>)

    /** Tombstones. `IN ()` is not valid SQL, so an empty page must not reach it. */
    suspend fun deleteByIds(ids: List<String>) {
        if (ids.isNotEmpty()) deleteByIdsOf(ids)
    }

    @Query("DELETE FROM synced_members WHERE id IN (:ids)")
    suspend fun deleteByIdsOf(ids: List<String>)

    /**
     * Drops rows an unfinished-and-restarted bootstrap did not touch.
     *
     * The only way a hard-deleted row ever leaves the device: sync can report a
     * soft delete as a tombstone, but a row that was removed outright leaves
     * nothing behind to report. Run only after a bootstrap has drained
     * completely — run early it would delete rows that simply had not arrived
     * yet.
     *
     * Not `retainOnly(ids)`. That form — `DELETE … WHERE id NOT IN (:keep)` — is
     * a trap once this table also holds locally created rows: they are in no
     * server response, so the first successful refresh deletes an unsent create.
     * A generation stamp has no such blind spot, but when local writes arrive
     * this query still needs `AND syncState = 0`.
     */
    @Query("DELETE FROM synced_members WHERE generation < :generation")
    suspend fun sweep(generation: Long)

    @Query("DELETE FROM synced_members")
    suspend fun deleteAll()
}
