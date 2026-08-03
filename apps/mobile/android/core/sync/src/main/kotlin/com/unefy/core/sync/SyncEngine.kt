package com.unefy.core.sync

import com.unefy.core.database.SyncCursorDao
import com.unefy.core.database.SyncCursorEntity
import com.unefy.core.database.SyncTransaction
import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiEndpoints
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import io.ktor.client.request.parameter
import kotlinx.coroutines.CancellationException
import javax.inject.Inject
import javax.inject.Singleton

/** What one drain of one collection came to. */
sealed interface SyncOutcome {
    /** Drained to the end. The mirror is as current as the server's watermark. */
    data object UpToDate : SyncOutcome

    /**
     * This account's role may not mirror this collection. Distinct from a failure
     * on purpose: a failure is worth retrying on the next doorbell, and this will
     * be refused every single time.
     */
    data object NotPermitted : SyncOutcome

    data class Failed(val error: ApiError) : SyncOutcome
}

/**
 * Brings one collection's mirror up to date.
 *
 * An interface so [SyncCoordinator] — whose job is deciding *when* to sync — can
 * be tested without a socket, and so a test of the coordinator's rules cannot
 * accidentally become a test of HTTP.
 */
fun interface SyncEngine {
    suspend fun sync(collection: SyncCollection): SyncOutcome
}

/**
 * Drains a collection's change feed into the local mirror.
 *
 * The whole design rests on one property, and the transaction below is there to
 * keep it: **a page of rows and the cursor that accounts for them land together,
 * or neither lands.** Advance the cursor without storing the rows and the server
 * will never send them again — a hole nothing can detect, because from the
 * server's side the client said it had them. The mirror would be quietly missing
 * members until the cursor aged out a fortnight later.
 *
 * This is the client half of the server's invariant that a sync page is always a
 * superset of what changed and never a subset (see backend/app/api/v1/sync.py):
 * duplicates are free, absences are unrecoverable.
 */
@Singleton
class DeltaSyncEngine @Inject constructor(
    private val apiClient: ApiClient,
    private val cursors: SyncCursorDao,
    private val transaction: SyncTransaction,
) : SyncEngine {

    override suspend fun sync(collection: SyncCollection): SyncOutcome =
        drain(collection, resume = cursors.get(collection.name), restarted = false)

    /**
     * @param resume the stored position, or null if this collection has never
     *   been synced on this device.
     * @param restarted true on the retry after the server rejected our cursor, so
     *   a second rejection reports a failure instead of restarting forever.
     */
    private suspend fun drain(
        collection: SyncCollection,
        resume: SyncCursorEntity?,
        restarted: Boolean,
    ): SyncOutcome {
        // "Has this device ever seen the whole collection?" — not "did this drain
        // start from scratch". A bootstrap interrupted by the app being killed
        // resumes from its stored cursor and is still a bootstrap, and it still
        // has to sweep when it finally reaches the end.
        val bootstrapping = resume == null || !resume.bootstrapComplete
        val generation = resume?.generation ?: FIRST_GENERATION

        var cursor: String? = resume?.cursor

        while (true) {
            val page = when (val result = fetch(collection.name, cursor)) {
                is ApiResult.Success -> result.data

                is ApiResult.Failure -> return when {
                    // The cursor is older than the server's tombstone retention,
                    // or was written by another account. Either way this device
                    // cannot know what it missed, so it re-reads everything under
                    // a new generation and sweeps whatever the re-read does not
                    // mention.
                    isCursorRejected(result.error) && !restarted -> drain(
                        collection,
                        resume = SyncCursorEntity(
                            collection = collection.name,
                            cursor = null,
                            bootstrapComplete = false,
                            generation = generation + 1,
                        ),
                        restarted = true,
                    )

                    result.error is ApiError.Forbidden -> SyncOutcome.NotPermitted

                    // Nothing was stored, so the cursor still points at the last
                    // page that actually landed and the next attempt asks for the
                    // same one again.
                    else -> SyncOutcome.Failed(result.error)
                }
            }

            val meta = page.meta.sync
            // The end of the feed — either the server says so, or it stopped
            // making progress. An empty page can legitimately carry `has_more`:
            // during a bootstrap the server withholds tombstones from the body
            // *after* applying its scan limit, so a stretch of deletions arrives
            // as empty pages whose cursor still moves. Stopping on emptiness was
            // the bug that left the mirror missing everyone sorted behind such a
            // stretch. What cannot legitimately happen is `has_more` with an
            // unmoved cursor — treating that as the end is what stops a
            // server-side bug from spinning this loop forever.
            val exhausted = !meta.hasMore || meta.cursor == cursor

            try {
                transaction.immediate {
                    collection.apply(
                        changed = page.data.changed,
                        deleted = page.data.deleted.map(SyncTombstone::id),
                        generation = generation,
                    )
                    // Swept inside the same transaction as the final page. A crash
                    // between the two would leave rows that were hard-deleted upstream
                    // sitting on the device until the next re-bootstrap — which may
                    // never come.
                    if (bootstrapping && exhausted) collection.sweep(generation)
                    cursors.upsert(
                        SyncCursorEntity(
                            collection = collection.name,
                            cursor = meta.cursor,
                            // Sticky: once the whole collection has been seen it stays
                            // seen, so a multi-page delta does not knock the device
                            // back into bootstrap state halfway through.
                            bootstrapComplete = resume?.bootstrapComplete == true || exhausted,
                            generation = generation,
                        ),
                    )
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                // A page that cannot be applied — a decode drift, a full disk —
                // is this collection's failure, not the sync loop's. The
                // transaction has rolled back, so the cursor still points at the
                // last page that landed; thrown instead of returned, this took
                // the coordinator's serving loop down and silently stopped every
                // collection's sync for the rest of the session.
                return SyncOutcome.Failed(ApiError.Unknown(e))
            }

            if (exhausted) return SyncOutcome.UpToDate
            cursor = meta.cursor
        }
    }

    private suspend fun fetch(collection: String, cursor: String?): ApiResult<SyncPage> =
        apiClient.getWhole(ApiEndpoints.sync(collection)) {
            if (cursor != null) parameter("cursor", cursor)
        }

    /**
     * A cursor the server will not take: too old (409 `CURSOR_TOO_OLD`) or
     * unparseable (400). Both recover the same way, and neither is worth retrying
     * as-is — asking again with the same token gets the same answer.
     */
    private fun isCursorRejected(error: ApiError): Boolean =
        error is ApiError.Http && (error.status == 409 || error.status == 400)

    private companion object {
        const val FIRST_GENERATION = 1L
    }
}
