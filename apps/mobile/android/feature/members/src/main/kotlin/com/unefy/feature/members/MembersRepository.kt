package com.unefy.feature.members

import com.unefy.core.database.SyncCursorDao
import com.unefy.core.database.SyncedMember
import com.unefy.core.database.SyncedMemberDao
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
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
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
    val gender: String? = null,
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
    gender = gender,
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

/**
 * A member's membership in an external federation (DSB, BDS, …). Read-only on
 * mobile; the detail screen shows it, nothing edits it. Lives in this feature
 * because no other screen has a reason to know about federations.
 */
data class FederationMembership(
    val id: String,
    val federation: String,
    val federationNumber: String?,
    val joinedAt: String?,
    val leftAt: String?,
)

@Serializable
internal data class FederationMembershipDto(
    val id: String,
    val federation: String,
    @SerialName("federation_number") val federationNumber: String? = null,
    @SerialName("joined_at") val joinedAt: String? = null,
    @SerialName("left_at") val leftAt: String? = null,
)

internal fun FederationMembershipDto.toDomain() = FederationMembership(
    id = id,
    federation = federation,
    federationNumber = federationNumber,
    joinedAt = joinedAt,
    leftAt = leftAt,
)

/**
 * A mirror row as the domain model.
 *
 * `iban = null` is not a gap in the mapping, it is the mirror's design: the local
 * database never holds a member's bank details. A screen that shows them fetches
 * the member over the network, and shows nothing there when offline — an empty
 * field rather than a wrong one.
 */
internal fun SyncedMember.toDomain() = Member(
    id = id,
    memberNumber = memberNumber,
    firstName = firstName,
    lastName = lastName,
    email = email,
    phone = phone,
    mobile = mobile,
    birthday = birthday,
    gender = gender,
    street = street,
    zipCode = zipCode,
    city = city,
    status = MemberStatus.fromApi(status),
    category = category,
    joinedAt = joinedAt,
    leftAt = leftAt,
    iban = null,
)

interface MembersRepository {

    /**
     * The member list, from the local mirror.
     *
     * A [Flow] rather than a call, and local rather than remote — the two changes
     * are one decision. `GET /api/v1/sync/members` has no search, no status filter
     * and no page numbers; it hands over the whole collection and then only what
     * changed. So filtering moves into SQL, and the screen stops asking for data
     * and starts watching it: a change synced in the background reaches the list
     * without the list requesting anything.
     *
     * No paging. Sync pages arrive in `(updated_at, id)` order while the list is
     * sorted by surname, so "one more page" would grow the list in the middle
     * rather than at the end — and a partly mirrored club means the search
     * silently fails to find people, which is precisely the failure the whole
     * design is built to avoid.
     */
    fun stream(query: String): Flow<List<Member>>

    /** How many the club has — a count of the mirror, not of what is on screen. */
    fun count(): Flow<Int>

    /**
     * Whether the mirror holds the whole collection, to tell "loading" from
     * "empty". True only once the bootstrap has drained to the end — a
     * partially-filled mirror is still "loading", or the header would announce
     * a fifth of the club as all of it.
     */
    fun hasSynced(): Flow<Boolean>

    /**
     * One member from the mirror, or null if it holds no such row.
     *
     * Carries no banking fields — those are not mirrored. A screen that needs them
     * asks [byId] as well and does so only when there is a connection.
     */
    fun byIdStream(id: String): Flow<Member?>

    /**
     * One member from the server, banking fields included.
     *
     * Still a one-shot call, and deliberately: the fields it adds are the ones
     * that must not be written to disk.
     */
    suspend fun byId(id: String): ApiResult<Member>

    /**
     * A member's federation memberships, from the server.
     *
     * Not mirrored: shown on one screen, changes rarely, and offline an absent
     * section reads better than a stale one.
     */
    suspend fun federations(id: String): ApiResult<List<FederationMembership>>

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
    private val members: SyncedMemberDao,
    private val cursors: SyncCursorDao,
) : MembersRepository {

    override fun stream(query: String): Flow<List<Member>> =
        members.search(query).map { rows -> rows.map(SyncedMember::toDomain) }

    override fun count(): Flow<Int> = members.countStream()

    override fun hasSynced(): Flow<Boolean> =
        cursors.bootstrapCompleteStream(MemberSyncCollection.COLLECTION)

    override fun byIdStream(id: String): Flow<Member?> =
        members.byIdStream(id).map { it?.toDomain() }

    override suspend fun byId(id: String): ApiResult<Member> = apiClient
        .get<MemberDto>(ApiEndpoints.member(id))
        .map(MemberDto::toDomain)

    override suspend fun federations(id: String): ApiResult<List<FederationMembership>> = apiClient
        .get<List<FederationMembershipDto>>(ApiEndpoints.memberFederations(id))
        .map { dtos -> dtos.map(FederationMembershipDto::toDomain) }

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
