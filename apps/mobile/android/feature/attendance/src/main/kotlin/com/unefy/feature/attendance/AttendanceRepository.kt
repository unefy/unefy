package com.unefy.feature.attendance

import com.unefy.core.database.CachedMember
import com.unefy.core.database.CachedMemberDao
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
import java.time.Instant
import javax.inject.Inject
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
    @SerialName("member_id") val memberId: String,
    val note: String? = null,
    @SerialName("checked_in_at") val checkedInAt: String? = null,
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
    @SerialName("member_id") val memberId: String,
    @SerialName("member_name") val memberName: String? = null,
    val method: String,
    @SerialName("checked_in_at") val checkedInAt: String,
)

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
    val memberId: String,
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
        memberId: String,
        checkedInAt: String? = null,
    ): ApiResult<ScanOutcome>

    suspend fun members(search: String?): ApiResult<List<MemberPick>>

    /** The session's attendance list, newest first. Cached for offline use. */
    suspend fun sessionRecords(sessionId: String): ApiResult<List<CheckedInEntry>>
}

@Singleton
class DefaultAttendanceRepository @Inject constructor(
    private val apiClient: ApiClient,
    private val memberCache: CachedMemberDao,
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
        memberId: String,
        checkedInAt: String?,
    ): ApiResult<ScanOutcome> = apiClient
        .post<ScanResultDto>(
            ApiEndpoints.attendanceCheckIn(sessionId),
            body = ManualCheckInRequest(memberId = memberId, checkedInAt = checkedInAt),
        )
        .map { ScanOutcome(it.memberName, it.memberNumber, it.assurance) }

    /**
     * The member list, from the network when possible and from the cache when
     * not.
     *
     * Cached because the supervisor's manual check-in list is useless without
     * it: queueing the write while the read stays online-only means an empty
     * list in exactly the basement the queue exists for. The cache is refreshed
     * on every successful load and only read when the network refuses — a
     * stale name is a far smaller problem than no name.
     */
    override suspend fun members(search: String?): ApiResult<List<MemberPick>> {
        val result = apiClient
            .get<List<MemberPickDto>>(ApiEndpoints.MEMBERS) {
                parameter("page", 1)
                parameter("per_page", MEMBER_PAGE_SIZE)
                if (!search.isNullOrBlank()) parameter("search", search)
            }
            .map { dtos ->
                dtos.map { MemberPick(it.id, it.memberNumber, "${it.firstName} ${it.lastName}") }
            }

        return when {
            result is ApiResult.Success -> {
                memberCache.upsert(result.data.map { CachedMember(it.id, it.memberNumber, it.name) })
                // Only after an unfiltered load: a search returns a subset, and
                // pruning to it would throw away everyone who did not match.
                if (search.isNullOrBlank()) {
                    memberCache.retainOnly(result.data.map(MemberPick::id))
                }
                result
            }

            // Only a dead connection falls back. A 403 means this account may
            // not list members, and answering it from a cache would be a lie.
            result is ApiResult.Failure && result.error is ApiError.Network ->
                ApiResult.Success(
                    memberCache.search(search.orEmpty(), MEMBER_PAGE_SIZE)
                        .map { MemberPick(it.id, it.memberNumber, it.name) },
                )

            else -> result
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

    private fun toEntry(row: CachedSessionRecord) = CheckedInEntry(
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
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class AttendanceModule {
    @Binds
    abstract fun bindAttendanceRepository(impl: DefaultAttendanceRepository): AttendanceRepository
}
