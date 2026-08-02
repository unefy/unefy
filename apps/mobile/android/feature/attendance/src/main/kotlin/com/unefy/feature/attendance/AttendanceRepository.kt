package com.unefy.feature.attendance

import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiEndpoints
import com.unefy.core.network.ApiResult
import com.unefy.core.network.map
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import io.ktor.client.request.parameter
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
)

@Serializable
internal data class ScanResultDto(
    val id: String,
    @SerialName("member_name") val memberName: String? = null,
    @SerialName("member_number") val memberNumber: String? = null,
    val assurance: String,
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

interface AttendanceRepository {
    suspend fun seed(): ApiResult<AttendanceSeed>

    /** Open sessions only — a closed one cannot take a check-in anyway. */
    suspend fun openSessions(): ApiResult<List<AttendanceSessionSummary>>

    suspend fun scan(
        sessionId: String,
        code: String,
        installId: String?,
        staffDeviceId: String?,
    ): ApiResult<ScanOutcome>
}

@Singleton
class DefaultAttendanceRepository @Inject constructor(
    private val apiClient: ApiClient,
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

    override suspend fun openSessions(): ApiResult<List<AttendanceSessionSummary>> = apiClient
        .get<List<AttendanceSessionDto>>(ApiEndpoints.ATTENDANCE_SESSIONS) {
            parameter("status", "open")
            parameter("per_page", SESSION_PAGE_SIZE)
        }
        .map { dtos ->
            dtos.map { AttendanceSessionSummary(it.id, it.title, it.location, it.recordCount) }
        }

    override suspend fun scan(
        sessionId: String,
        code: String,
        installId: String?,
        staffDeviceId: String?,
    ): ApiResult<ScanOutcome> = apiClient
        .post<ScanResultDto>(
            ApiEndpoints.attendanceScan(sessionId),
            body = ScanRequest(code = code, installId = installId, staffDeviceId = staffDeviceId),
        )
        .map { ScanOutcome(it.memberName, it.memberNumber, it.assurance) }

    private companion object {
        const val SESSION_PAGE_SIZE = 50
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class AttendanceModule {
    @Binds
    abstract fun bindAttendanceRepository(impl: DefaultAttendanceRepository): AttendanceRepository
}
