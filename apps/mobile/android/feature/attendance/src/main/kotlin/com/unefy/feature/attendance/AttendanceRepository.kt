package com.unefy.feature.attendance

import com.unefy.core.database.SyncCursorDao
import com.unefy.core.database.SyncedMemberDao
import com.unefy.core.database.CachedSession
import com.unefy.core.database.CachedSessionDao
import com.unefy.core.database.CachedSessionRecord
import com.unefy.core.database.CachedSessionRecordDao
import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiEndpoints
import com.unefy.core.network.ApiResult
import com.unefy.core.network.map
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import io.ktor.client.request.parameter
import io.ktor.http.encodeURLParameter
import java.time.Instant
import javax.inject.Inject
import kotlinx.coroutines.flow.first
import javax.inject.Singleton
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Everything the app needs to build its own check-in codes. Mirrors the
 * backend's `AttendanceSeedResponse` — including the tenant, because the MAC is
 * taken over it and reading it from the session instead would be a second
 * source that could drift.
 */
@Serializable
internal data class AttendanceSeedDto(
    @SerialName("member_ref") val memberRef: String,
    val seed: String,
    @SerialName("tenant_id") val tenantId: String,
    @SerialName("expires_at") val expiresAt: Long,
    @SerialName("interval_seconds") val intervalSeconds: Long,
    val algorithm: String,
)

@Serializable
internal data class AttendanceSessionDto(
    val id: String,
    val title: String,
    val location: String? = null,
    @SerialName("opens_at") val opensAt: String,
    @SerialName("closes_at") val closesAt: String,
    val status: String,
    @SerialName("record_count") val recordCount: Int = 0,
)

@Serializable
internal data class ScanRequest(
    val code: String,
    @SerialName("install_id") val installId: String?,
    @SerialName("staff_device_id") val staffDeviceId: String?,
    /**
     * Only set when draining the queue. Absent means "this is happening now",
     * and the server uses its own clock — which is the honest answer for a live
     * check-in and the wrong one for a buffered scan taken twenty minutes ago.
     */
    @SerialName("checked_in_at") val checkedInAt: String? = null,
)

@Serializable
internal data class ScanResultDto(
    val id: String,
    @SerialName("member_name") val memberName: String? = null,
    @SerialName("member_number") val memberNumber: String? = null,
    val assurance: String,
)

@Serializable
internal data class ManualCheckInRequest(
    /** Client-assigned record id — a replayed drain is a retry, not a second person. */
    val id: String? = null,
    // Exactly one of the two, mirroring the backend's CHECK.
    @SerialName("member_id") val memberId: String? = null,
    @SerialName("guest_name") val guestName: String? = null,
    val note: String? = null,
    @SerialName("checked_in_at") val checkedInAt: String? = null,
)

@Serializable
internal data class CreateSessionRequest(
    val title: String,
    @SerialName("opens_at") val opensAt: String,
    @SerialName("closes_at") val closesAt: String,
)

/**
 * Just enough of a member to pick one off a list.
 *
 * Its own DTO rather than reusing `feature:members` — features never depend on
 * each other (see apps/mobile/CLAUDE.md), and this is a different projection
 * anyway: a name to tap, not a profile.
 */
@Serializable
internal data class MemberPickDto(
    val id: String,
    @SerialName("member_number") val memberNumber: String,
    @SerialName("first_name") val firstName: String,
    @SerialName("last_name") val lastName: String,
)

@Serializable
internal data class SessionRecordDto(
    val id: String,
    // Null for a guest. Declaring it non-null made the whole list fail to
    // decode the moment one guest was in the session — not just the guest.
    @SerialName("member_id") val memberId: String? = null,
    @SerialName("member_name") val memberName: String? = null,
    val method: String,
    @SerialName("checked_in_at") val checkedInAt: String,
)

@Serializable
internal data class MyRecordDto(
    val id: String,
    @SerialName("session_title") val sessionTitle: String? = null,
    @SerialName("checked_in_at") val checkedInAt: String,
)

/** The member's own most recent check-in, for confirming one just happened. */
data class OwnCheckIn(val sessionTitle: String?, val checkedInAtEpochSeconds: Long)

/** The seed plus the parameters it is valid under. */
data class AttendanceSeed(
    val memberRef: String,
    val seed: String,
    val tenantId: String,
    val expiresAtEpochSeconds: Long,
)

data class AttendanceSessionSummary(
    val id: String,
    val title: String,
    val location: String?,
    val recordCount: Int,
)

data class ScanOutcome(val memberName: String?, val memberNumber: String?, val assurance: String)

/**
 * Somebody already checked into a session — one line of the attendance list.
 *
 * `pending` marks a check-in this device is still holding. Shown alongside the
 * confirmed ones rather than in a separate place: to the supervisor the person
 * is in the room either way, and splitting the list would invite them to check
 * someone in twice.
 */
data class CheckedInEntry(
    /** Stable across refreshes: the record id, or the queue row for a pending one. */
    val key: String,
    /** Null for a guest, who has no member record. */
    val memberId: String?,
    val memberName: String,
    val method: String,
    val checkedInAtEpochSeconds: Long,
    val pending: Boolean = false,
)

/** A member as shown in the manual pick list. */
data class MemberPick(
    val id: String,
    val memberNumber: String,
    val name: String,
)

interface AttendanceRepository {
    suspend fun seed(): ApiResult<AttendanceSeed>

    /** Open sessions only — a closed one cannot take a check-in anyway. */
    suspend fun openSessions(): ApiResult<List<AttendanceSessionSummary>>

    suspend fun scan(
        sessionId: String,
        code: String,
        installId: String?,
        staffDeviceId: String?,
        checkedInAt: String? = null,
    ): ApiResult<ScanOutcome>

    /**
     * The supervisor ticking a box, for whoever turned up without a working
     * phone. Records as `manual` / `low` — the backend derives that from the
     * method, the app cannot claim otherwise.
     */
    suspend fun checkInManually(
        sessionId: String,
        memberId: String? = null,
        guestName: String? = null,
        checkedInAt: String? = null,
        clientId: String? = null,
    ): ApiResult<ScanOutcome>

    /**
     * Opens a session from the app.
     *
     * Needed because a supervisor standing at the range with no open session
     * has no way forward at all — the scanner shows an empty screen and the
     * evening goes unrecorded unless somebody reaches a laptop.
     */
    suspend fun createSession(
        title: String,
        opensAt: String,
        closesAt: String,
    ): ApiResult<AttendanceSessionSummary>

    suspend fun members(search: String?): ApiResult<List<MemberPick>>

    /** The session's attendance list, newest first. Cached for offline use. */
    suspend fun sessionRecords(sessionId: String): ApiResult<List<CheckedInEntry>>

    /**
     * The caller's own latest check-in, or null if they have none.
     *
     * The member's phone has no other way of learning that it was scanned —
     * the code goes out through a camera and the check-in happens on somebody
     * else's device. Without this the screen holding out a QR can never say
     * whether it worked.
     */
    suspend fun latestOwnCheckIn(): ApiResult<OwnCheckIn?>

    /**
     * Takes a check-in back.
     *
     * A soft delete with an audit entry, never a removal — and refused by the
     * server once the session is closed, which is what keeps the freeze
     * meaningful. The reason is optional: inside an open session this is nearly
     * always somebody undoing a mistap, and the audit entry's own actor and
     * timestamp are what make that verifiable.
     */
    suspend fun deleteRecord(recordId: String, reason: String? = null): ApiResult<Unit>
}

@Singleton
class DefaultAttendanceRepository @Inject constructor(
    private val apiClient: ApiClient,
    private val syncedMembers: SyncedMemberDao,
    private val syncCursors: SyncCursorDao,
    private val sessionCache: CachedSessionDao,
    private val recordCache: CachedSessionRecordDao,
) : AttendanceRepository {

    override suspend fun seed(): ApiResult<AttendanceSeed> = apiClient
        .get<AttendanceSeedDto>(ApiEndpoints.ATTENDANCE_ME_SEED)
        .map { dto ->
            AttendanceSeed(
                memberRef = dto.memberRef,
                seed = dto.seed,
                tenantId = dto.tenantId,
                expiresAtEpochSeconds = dto.expiresAt,
            )
        }

    /**
     * Open sessions, cached. Without this the scanner has nothing to check into
     * offline, and with nothing to check into the queue never gets a chance to
     * hold anything.
     */
    override suspend fun openSessions(): ApiResult<List<AttendanceSessionSummary>> {
        val result = apiClient
            .get<List<AttendanceSessionDto>>(ApiEndpoints.ATTENDANCE_SESSIONS) {
                parameter("status", "open")
                parameter("per_page", SESSION_PAGE_SIZE)
            }
            .map { dtos ->
                dtos.map { AttendanceSessionSummary(it.id, it.title, it.location, it.recordCount) }
            }

        return when {
            result is ApiResult.Success -> {
                sessionCache.upsert(
                    result.data.map { CachedSession(it.id, it.title, it.location, it.recordCount) },
                )
                // Prunes what closed upstream — an offline scan into a closed
                // session is only refused later.
                sessionCache.retainOnly(result.data.map(AttendanceSessionSummary::id))
                result
            }

            result is ApiResult.Failure && result.error is ApiError.Network ->
                ApiResult.Success(
                    sessionCache.all()
                        .map { AttendanceSessionSummary(it.id, it.title, it.location, it.recordCount) },
                )

            else -> result
        }
    }

    override suspend fun scan(
        sessionId: String,
        code: String,
        installId: String?,
        staffDeviceId: String?,
        checkedInAt: String?,
    ): ApiResult<ScanOutcome> = apiClient
        .post<ScanResultDto>(
            ApiEndpoints.attendanceScan(sessionId),
            body = ScanRequest(
                code = code,
                installId = installId,
                staffDeviceId = staffDeviceId,
                checkedInAt = checkedInAt,
            ),
        )
        .map { ScanOutcome(it.memberName, it.memberNumber, it.assurance) }

    override suspend fun checkInManually(
        sessionId: String,
        memberId: String?,
        guestName: String?,
        checkedInAt: String?,
        clientId: String?,
    ): ApiResult<ScanOutcome> = apiClient
        .post<ScanResultDto>(
            ApiEndpoints.attendanceCheckIn(sessionId),
            body = ManualCheckInRequest(
                id = clientId,
                memberId = memberId,
                guestName = guestName,
                checkedInAt = checkedInAt,
            ),
        )
        .map { ScanOutcome(it.memberName, it.memberNumber, it.assurance) }

    override suspend fun createSession(
        title: String,
        opensAt: String,
        closesAt: String,
    ): ApiResult<AttendanceSessionSummary> = apiClient
        .post<AttendanceSessionDto>(
            ApiEndpoints.ATTENDANCE_SESSIONS,
            body = CreateSessionRequest(title, opensAt, closesAt),
        )
        .map { AttendanceSessionSummary(it.id, it.title, it.location, it.recordCount) }

    /**
     * The member list, from the mirror.
     *
     * This used to be its own cache (`cached_members`) with a network-first
     * read, built for one concrete failure: the supervisor's manual check-in
     * list came up empty in a basement. The member mirror answers the same
     * need strictly better — complete rather than the last page that happened
     * to load, current within a doorbell rather than a visit, searched with
     * the umlaut folding the member list already uses, and cleared on
     * sign-out with everything else.
     *
     * The network path survives only for the gap the mirror cannot cover: a
     * fresh sign-in whose bootstrap has not finished yet.
     */
    override suspend fun members(search: String?): ApiResult<List<MemberPick>> {
        if (syncCursors.bootstrapCompleteStream(MEMBERS_COLLECTION).first()) {
            return ApiResult.Success(
                syncedMembers.search(search.orEmpty()).first()
                    .take(MEMBER_PAGE_SIZE)
                    .map { MemberPick(it.id, it.memberNumber, "${it.firstName} ${it.lastName}") },
            )
        }

        return apiClient
            .get<List<MemberPickDto>>(ApiEndpoints.MEMBERS) {
                parameter("page", 1)
                parameter("per_page", MEMBER_PAGE_SIZE)
                if (!search.isNullOrBlank()) parameter("search", search)
            }
            .map { dtos ->
                dtos.map { MemberPick(it.id, it.memberNumber, "${it.firstName} ${it.lastName}") }
            }
    }

    override suspend fun sessionRecords(sessionId: String): ApiResult<List<CheckedInEntry>> {
        val result = apiClient
            .get<List<SessionRecordDto>>(ApiEndpoints.attendanceRecords(sessionId))
            .map { records ->
                records.map { dto ->
                    CachedSessionRecord(
                        id = dto.id,
                        sessionId = sessionId,
                        memberId = dto.memberId,
                        memberName = dto.memberName.orEmpty(),
                        method = dto.method,
                        checkedInAtEpochSeconds = parseInstant(dto.checkedInAt),
                    )
                }
            }

        return when {
            result is ApiResult.Success -> {
                recordCache.upsert(result.data)
                recordCache.retainOnly(sessionId, result.data.map(CachedSessionRecord::id))
                ApiResult.Success(recordCache.forSession(sessionId).map(::toEntry))
            }

            result is ApiResult.Failure && result.error is ApiError.Network ->
                ApiResult.Success(recordCache.forSession(sessionId).map(::toEntry))

            else -> result as ApiResult.Failure
        }
    }

    override suspend fun latestOwnCheckIn(): ApiResult<OwnCheckIn?> = apiClient
        .get<List<MyRecordDto>>(ApiEndpoints.ATTENDANCE_ME_RECORDS) {
            parameter("page", 1)
            parameter("per_page", 1)
        }
        .map { records ->
            records.firstOrNull()?.let {
                OwnCheckIn(it.sessionTitle, parseInstant(it.checkedInAt))
            }
        }

    override suspend fun deleteRecord(recordId: String, reason: String?): ApiResult<Unit> =
        apiClient.deleteNoContent(
            ApiEndpoints.attendanceRecord(recordId) +
                if (reason.isNullOrBlank()) "" else "?reason=${reason.encodeURLParameter()}",
        )

    private fun toEntry(row: CachedSessionRecord) = CheckedInEntry(
        key = row.id,
        memberId = row.memberId,
        memberName = row.memberName,
        method = row.method,
        checkedInAtEpochSeconds = row.checkedInAtEpochSeconds,
    )

    /** A time the server sent. Unparseable means 0 — sorts last, never crashes. */
    private fun parseInstant(value: String): Long =
        runCatching { Instant.parse(value).epochSecond }.getOrDefault(0L)

    private companion object {
        const val SESSION_PAGE_SIZE = 50

        // The list is searchable, so this is a ceiling for "show me everyone",
        // not a page the user is expected to scroll to the end of.
        const val MEMBER_PAGE_SIZE = 100

        /**
         * The sync collection whose mirror answers the pick list. The name is
         * the sync contract's (backend/app/sync/registry.py); feature:members
         * owns the collection class, and module rules forbid reaching into it
         * for the constant.
         */
        const val MEMBERS_COLLECTION = "members"
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class AttendanceModule {
    @Binds
    abstract fun bindAttendanceRepository(impl: DefaultAttendanceRepository): AttendanceRepository
}
