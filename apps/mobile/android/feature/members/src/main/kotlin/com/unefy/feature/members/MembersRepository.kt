package com.unefy.feature.members

import com.unefy.core.model.Member
import com.unefy.core.model.DirectoryEntry
import com.unefy.core.model.MemberStatus
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
 * Hand-written DTO mirroring the backend's `MemberResponse`. Deliberately a
 * subset — see the shared API contract note in apps/mobile/CLAUDE.md. Unknown
 * fields are ignored by the Json config, so backend additions do not break the
 * app; a CI test against the OpenAPI spec is what catches removals.
 */
@Serializable
internal data class MemberDto(
    val id: String,
    @SerialName("member_number") val memberNumber: String,
    @SerialName("first_name") val firstName: String,
    @SerialName("last_name") val lastName: String,
    val email: String? = null,
    val phone: String? = null,
    val mobile: String? = null,
    val birthday: String? = null,
    val street: String? = null,
    @SerialName("zip_code") val zipCode: String? = null,
    val city: String? = null,
    val status: String? = null,
    val category: String? = null,
    @SerialName("joined_at") val joinedAt: String = "",
    @SerialName("left_at") val leftAt: String? = null,
    val iban: String? = null,
)

internal fun MemberDto.toDomain() = Member(
    id = id,
    memberNumber = memberNumber,
    firstName = firstName,
    lastName = lastName,
    email = email,
    phone = phone,
    mobile = mobile,
    birthday = birthday,
    street = street,
    zipCode = zipCode,
    city = city,
    status = MemberStatus.fromApi(status),
    category = category,
    joinedAt = joinedAt,
    leftAt = leftAt,
    iban = iban,
)

/**
 * An interface, not a class: the ViewModel tests substitute a fake here. Same
 * reason the iOS side is protocol-oriented — see apps/mobile/CLAUDE.md.
 */
@Serializable
internal data class DirectoryDto(
    val id: String,
    @SerialName("first_name") val firstName: String,
    @SerialName("last_name") val lastName: String,
    val category: String? = null,
)

internal fun DirectoryDto.toDomain() = DirectoryEntry(id, firstName, lastName, category)

interface MembersRepository {
    /** Administrative: the full list, board and above only. */
    suspend fun list(page: Int = 1, perPage: Int = 50, search: String? = null): ApiResult<List<Member>>

    suspend fun byId(id: String): ApiResult<Member>

    /** Self-service: the caller's own record, whatever their role. */
    suspend fun me(): ApiResult<Member>

    /** Member-facing: names and category of active members, nothing else. */
    suspend fun directory(
        page: Int = 1,
        perPage: Int = 100,
        search: String? = null,
    ): ApiResult<List<DirectoryEntry>>
}

@Singleton
class DefaultMembersRepository @Inject constructor(
    private val apiClient: ApiClient,
) : MembersRepository {
    override suspend fun list(
        page: Int,
        perPage: Int,
        search: String?,
    ): ApiResult<List<Member>> = apiClient
        .get<List<MemberDto>>(ApiEndpoints.MEMBERS) {
            parameter("page", page)
            parameter("per_page", perPage)
            if (!search.isNullOrBlank()) parameter("search", search)
        }
        .map { dtos -> dtos.map(MemberDto::toDomain) }

    override suspend fun byId(id: String): ApiResult<Member> = apiClient
        .get<MemberDto>(ApiEndpoints.member(id))
        .map(MemberDto::toDomain)

    override suspend fun me(): ApiResult<Member> = apiClient
        .get<MemberDto>(ApiEndpoints.MEMBERS_ME)
        .map(MemberDto::toDomain)

    override suspend fun directory(
        page: Int,
        perPage: Int,
        search: String?,
    ): ApiResult<List<DirectoryEntry>> = apiClient
        .get<List<DirectoryDto>>(ApiEndpoints.MEMBERS_DIRECTORY) {
            parameter("page", page)
            parameter("per_page", perPage)
            if (!search.isNullOrBlank()) parameter("search", search)
        }
        .map { dtos -> dtos.map(DirectoryDto::toDomain) }

}

@Module
@InstallIn(SingletonComponent::class)
abstract class MembersModule {
    @Binds
    abstract fun bindMembersRepository(impl: DefaultMembersRepository): MembersRepository
}
