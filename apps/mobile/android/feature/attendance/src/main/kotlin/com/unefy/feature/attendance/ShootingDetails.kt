package com.unefy.feature.attendance

import com.unefy.core.network.ApiClient
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
 * The shooting module's record details, as the scanner needs them.
 *
 * In `feature:attendance` rather than a module of its own because there is no
 * `feature:shooting` on Android and the only place that enters these fields is
 * the attendance list at the range. Kept in its own file so the boundary stays
 * visible: everything here is behind `require_module("shooting")` on the server
 * and 403s for a club without it.
 *
 * Deliberately online-only, unlike the check-in beside it. A check-in is taken at
 * the door and cannot wait for a connection — that is why there is a queue. What
 * somebody shot is filled in afterwards at the range table, and a second write
 * queue with its own conflict rules would cost far more than it buys.
 */
@Serializable
internal data class ShootingDetailDto(
    val id: String,
    @SerialName("attendance_record_id") val attendanceRecordId: String,
    @SerialName("club_discipline_id") val clubDisciplineId: String? = null,
    @SerialName("weapon_category") val weaponCategory: String? = null,
    @SerialName("rounds_fired") val roundsFired: Int? = null,
)

@Serializable
internal data class ShootingDetailBody(
    @SerialName("club_discipline_id") val clubDisciplineId: String?,
    @SerialName("weapon_category") val weaponCategory: String?,
    @SerialName("rounds_fired") val roundsFired: Int?,
)

@Serializable
internal data class ClubDisciplineDto(
    val id: String,
    val name: String,
    @SerialName("short_name") val shortName: String? = null,
)

/** What somebody shot at one attendance. Every field optional — the board fills
 *  in what it knows, and an evening with only a round count is still useful. */
data class ShootingDetail(
    val attendanceRecordId: String,
    val clubDisciplineId: String?,
    val weaponCategory: String?,
    val roundsFired: Int?,
)

/** A discipline the club actually offers. */
data class ClubDiscipline(
    val id: String,
    val name: String,
    val shortName: String?,
)

/**
 * The weapon categories the server accepts, in its own order.
 *
 * Mirrors `WEAPON_CATEGORY_PATTERN` in backend/app/schemas/shooting.py. A value
 * this list does not know is displayed as it arrives rather than dropped — the
 * server is allowed to be a version ahead.
 */
val WEAPON_CATEGORIES = listOf("kurzwaffe", "langwaffe", "luftdruck")

interface ShootingDetailRepository {
    /** Every detail of one session, keyed by attendance record. */
    suspend fun forSession(sessionId: String): ApiResult<Map<String, ShootingDetail>>

    /** The club's disciplines, for the picker. */
    suspend fun disciplines(): ApiResult<List<ClubDiscipline>>

    /**
     * Upsert: the first save creates the row.
     *
     * Nulls are sent, not omitted, so a wrong entry can be cleared. A form whose
     * values can only ever be added to is a trap.
     */
    suspend fun save(
        recordId: String,
        clubDisciplineId: String?,
        weaponCategory: String?,
        roundsFired: Int?,
    ): ApiResult<ShootingDetail>
}

@Singleton
class DefaultShootingDetailRepository @Inject constructor(
    private val apiClient: ApiClient,
) : ShootingDetailRepository {

    override suspend fun forSession(
        sessionId: String,
    ): ApiResult<Map<String, ShootingDetail>> = apiClient
        .get<List<ShootingDetailDto>>(SHOOTING_RECORDS) { parameter("session_id", sessionId) }
        .map { dtos -> dtos.associate { it.attendanceRecordId to it.toDomain() } }

    override suspend fun disciplines(): ApiResult<List<ClubDiscipline>> = apiClient
        .get<List<ClubDisciplineDto>>(CLUB_DISCIPLINES)
        .map { dtos -> dtos.map { ClubDiscipline(it.id, it.name, it.shortName) } }

    override suspend fun save(
        recordId: String,
        clubDisciplineId: String?,
        weaponCategory: String?,
        roundsFired: Int?,
    ): ApiResult<ShootingDetail> = apiClient
        .patch<ShootingDetailDto>(
            "$SHOOTING_RECORDS/$recordId",
            ShootingDetailBody(clubDisciplineId, weaponCategory, roundsFired),
        )
        .map(ShootingDetailDto::toDomain)

    private companion object {
        const val SHOOTING_RECORDS = "/api/v1/modules/shooting/records"
        const val CLUB_DISCIPLINES = "/api/v1/club-disciplines"
    }
}

private fun ShootingDetailDto.toDomain() = ShootingDetail(
    attendanceRecordId = attendanceRecordId,
    clubDisciplineId = clubDisciplineId,
    weaponCategory = weaponCategory,
    roundsFired = roundsFired,
)

@Module
@InstallIn(SingletonComponent::class)
abstract class ShootingDetailModule {
    @Binds
    abstract fun bind(impl: DefaultShootingDetailRepository): ShootingDetailRepository
}
