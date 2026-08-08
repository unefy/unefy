package com.unefy.feature.attendance

import com.unefy.core.database.PendingCheckIn
import com.unefy.core.database.PendingCheckInDao
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import com.unefy.core.sync.WriteQueue
import java.time.Instant
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow

/** What became of one check-in attempt. */
sealed interface CheckInResult {
    data class Recorded(val outcome: ScanOutcome) : CheckInResult

    /** No connection. Held on the device and sent when there is one. */
    data object Queued : CheckInResult

    /** The server said no, and will keep saying no. Nothing was queued. */
    data class Rejected(val error: ApiError) : CheckInResult
}

/**
 * Check-ins that survive a dead connection.
 *
 * A shooting range is usually a basement, so losing the network mid-evening is
 * the normal case rather than the exception. Without this, every scan taken
 * during the outage is simply gone — and unlike a failed read, a lost check-in
 * cannot be noticed later: nobody knows to look for it.
 *
 * The device's clock is captured at the moment of the check-in and sent with
 * the row when it finally goes out, because by then the server's clock says
 * something else. The backend keeps the two apart as `checked_in_at` and
 * `synced_at`, so an audit can tell a live check-in from a drained queue.
 *
 * Only a network failure queues. A refusal — expired code, wrong session, no
 * such member — is queued nowhere, because retrying it later cannot change the
 * answer and a queue that never drains is worse than an error.
 */
@Singleton
class CheckInQueue @Inject constructor(
    private val repository: AttendanceRepository,
    private val dao: PendingCheckInDao,
    private val clock: AttendanceClock,
    /** Drained first, so an evening exists before its check-ins — see [sync]. */
    private val writes: WriteQueue,
    /**
     * Null in unit tests. Scheduling is a side effect on the platform, and the
     * queue's rules are worth testing without one.
     */
    private val scheduler: SyncScheduler? = null,
) {
    val pendingCount: Flow<Int> = dao.countStream()

    suspend fun isEmpty(): Boolean = dao.all().isEmpty()

    suspend fun scan(
        sessionId: String,
        code: String,
        installId: String?,
    ): CheckInResult {
        val at = clock.epochSeconds()
        return submit(
            attempt = { repository.scan(sessionId, code, installId, installId) },
            enqueue = {
                PendingCheckIn(
                    sessionId = sessionId,
                    code = code,
                    checkedInAtEpochSeconds = at,
                    installId = installId,
                )
            },
        )
    }

    suspend fun checkInManually(
        sessionId: String,
        member: MemberPick,
        installId: String?,
    ): CheckInResult {
        val at = clock.epochSeconds()
        // Minted before the live attempt and reused by every retry of the
        // queued row: the server dedupes check-ins by this id, so even a live
        // attempt whose *response* was lost cannot double-book once the queue
        // drains.
        val clientId = UUID.randomUUID().toString()
        return submit(
            attempt = {
                repository.checkInManually(sessionId, memberId = member.id, clientId = clientId)
            },
            enqueue = {
                PendingCheckIn(
                    sessionId = sessionId,
                    memberId = member.id,
                    memberLabel = member.name,
                    checkedInAtEpochSeconds = at,
                    installId = installId,
                    clientId = clientId,
                )
            },
        )
    }

    /**
     * A guest, named rather than identified.
     *
     * Queues like any other check-in — somebody who is not a member is exactly
     * as present, and losing them to a dropped connection would be the same
     * loss.
     */
    suspend fun checkInGuest(
        sessionId: String,
        guestName: String,
        installId: String?,
    ): CheckInResult {
        val at = clock.epochSeconds()
        // Same id live and queued — see [checkInManually].
        val clientId = UUID.randomUUID().toString()
        return submit(
            attempt = {
                repository.checkInManually(sessionId, guestName = guestName, clientId = clientId)
            },
            enqueue = {
                PendingCheckIn(
                    sessionId = sessionId,
                    guestName = guestName,
                    memberLabel = guestName,
                    checkedInAtEpochSeconds = at,
                    installId = installId,
                    clientId = clientId,
                )
            },
        )
    }

    private suspend fun submit(
        attempt: suspend () -> ApiResult<ScanOutcome>,
        enqueue: () -> PendingCheckIn,
    ): CheckInResult = when (val result = attempt()) {
        is ApiResult.Success -> CheckInResult.Recorded(result.data)

        is ApiResult.Failure ->
            if (result.error is ApiError.Network) {
                dao.insert(enqueue())
                // Hands the drain to the platform, so it happens when the
                // network returns rather than when someone next opens a screen.
                scheduler?.scheduleDrain()
                CheckInResult.Queued
            } else {
                CheckInResult.Rejected(result.error)
            }
    }

    /**
     * Sends everything held, oldest first, and returns how many got through.
     *
     * Stops at the first network failure rather than working through the rest:
     * if one request could not reach the server, neither will the next, and
     * hammering a dead connection only delays the screen.
     */
    suspend fun sync(): Int {
        // The evening before the people in it. An evening opened at the range
        // is itself a queued write, and a check-in whose session the server has
        // never heard of comes back a 404 — which this queue keeps and marks
        // rather than drops, so it would heal on the next drain, but only after
        // an error nobody could explain. Sending them in order avoids the
        // question. Failures here are the write queue's business, not ours.
        writes.drain()

        var sent = 0
        for (entry in dao.all()) {
            val result = send(entry)

            when {
                result is ApiResult.Success -> {
                    dao.delete(entry.id)
                    sent++
                }

                // Already recorded — someone scanned them again while this row
                // waited, or a previous drain got through and the delete did
                // not. Either way the person is in, so the row is done.
                isAlreadyCheckedIn(result) -> dao.delete(entry.id)

                isOffline(result) -> return sent

                // Kept rather than dropped: a check-in that the server refuses
                // is still evidence that someone was there, and silently
                // discarding it is the one outcome nobody could notice.
                else -> dao.recordFailure(entry.id, describe(result))
            }
        }
        return sent
    }

    suspend fun pendingFor(sessionId: String): List<PendingCheckIn> = dao.forSession(sessionId)

    /**
     * Drops a queued check-in that was a mistake.
     *
     * The only place a check-in is ever really destroyed rather than
     * soft-deleted, and it is sound precisely because this one never reached a
     * server: there is no record to correct and no trail to keep consistent
     * with. Once sent, correction goes through the audited path instead.
     */
    suspend fun discard(id: Long) = dao.delete(id)

    private suspend fun send(entry: PendingCheckIn): ApiResult<ScanOutcome> {
        val at = Instant.ofEpochSecond(entry.checkedInAtEpochSeconds).toString()
        // Bound to locals: the entity lives in another module, so the compiler
        // will not smart-cast its properties across the null check.
        val code = entry.code
        val memberId = entry.memberId
        val guestName = entry.guestName

        return when {
            code != null -> repository.scan(
                sessionId = entry.sessionId,
                code = code,
                installId = entry.installId,
                staffDeviceId = entry.installId,
                checkedInAt = at,
            )

            memberId != null -> repository.checkInManually(
                sessionId = entry.sessionId,
                memberId = memberId,
                checkedInAt = at,
                clientId = entry.clientId,
            )

            guestName != null -> repository.checkInManually(
                sessionId = entry.sessionId,
                guestName = guestName,
                checkedInAt = at,
                // The whole reason the id exists: a drain that dies after the
                // server booked the guest but before the row was deleted must
                // not book them again on the retry.
                clientId = entry.clientId,
            )

            // Neither, which the schema should make impossible. Reported as a
            // refusal so the row stops being retried and stays visible.
            else -> ApiResult.Failure(ApiError.NotFound(code = null))
        }
    }

    private fun isOffline(result: ApiResult<ScanOutcome>) =
        result is ApiResult.Failure && result.error is ApiError.Network

    private fun isAlreadyCheckedIn(result: ApiResult<ScanOutcome>): Boolean {
        val error = (result as? ApiResult.Failure)?.error
        return error is ApiError.Http && error.code == ALREADY_CHECKED_IN
    }

    private fun describe(result: ApiResult<ScanOutcome>): String? =
        ((result as? ApiResult.Failure)?.error as? ApiError.Http)?.code

    private companion object {
        const val ALREADY_CHECKED_IN = "ALREADY_CHECKED_IN"
    }
}

/**
 * Asks the platform to drain the queue once there is a connection.
 *
 * An interface so the queue does not depend on WorkManager directly — the
 * decision *that* a drain is due belongs to the queue, the machinery for
 * surviving process death does not.
 */
fun interface SyncScheduler {
    fun scheduleDrain()
}
