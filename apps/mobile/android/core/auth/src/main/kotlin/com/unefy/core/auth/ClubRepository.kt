package com.unefy.core.auth

import com.unefy.core.model.Club
import com.unefy.core.model.ClubSport
import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiEndpoints
import com.unefy.core.network.ApiResult
import com.unefy.core.network.map
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
internal data class ClubDto(
    val id: String,
    val name: String,
    @SerialName("short_name") val shortName: String? = null,
    val sports: List<ClubSportDto> = emptyList(),
    val modules: List<String> = emptyList(),
)

@Serializable
internal data class ClubSportDto(
    val id: String,
    val key: String,
    val name: String,
    @SerialName("is_primary") val isPrimary: Boolean = false,
)

internal fun ClubDto.toDomain() = Club(
    id = id,
    name = name,
    shortName = shortName,
    sports = sports.map { ClubSport(it.id, it.key, it.name, it.isPrimary) },
    modules = modules,
)

/**
 * The club context of the signed-in session — which club, and which sport
 * modules it has active.
 *
 * Lives beside the session rather than in a feature module because it is not a
 * feature: it decides which features exist at all. A club with no sport
 * assigned has no modules, and the app is then purely generic. That is the
 * correct default, not a missing configuration.
 */
@Singleton
class ClubRepository @Inject constructor(
    private val apiClient: ApiClient,
) {
    suspend fun current(): ApiResult<Club> = apiClient
        .get<ClubDto>(ApiEndpoints.CLUB)
        .map(ClubDto::toDomain)
}
