package com.unefy.feature.members

import com.unefy.core.database.PendingWrite
import com.unefy.core.database.SyncCursorDao
import com.unefy.core.database.SyncedMember
import com.unefy.core.database.SyncedMemberDao
import com.unefy.core.database.foldForSearch
import com.unefy.core.model.Member
import com.unefy.core.model.DirectoryEntry
import com.unefy.core.model.MemberStatus
import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiEndpoints
import com.unefy.core.network.ApiResult
import com.unefy.core.network.map
import com.unefy.core.sync.WriteQueue
import java.util.UUID
import kotlinx.coroutines.flow.combine
import kotlinx.serialization.json.Json
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

    /**
     * Save a member, into the local queue.
     *
     * Returns the record's id — freshly generated for a new member, so the
     * caller can open the detail screen of somebody the server has never heard
     * of. [id] null means create.
     *
     * Cannot fail and does not touch the network: a clubhouse cellar is where
     * half of this gets typed. What reaches the server, and when, is the
     * queue's business.
     */
    suspend fun save(id: String?, draft: MemberDraft): String

    /** The ids with an unsent write, so a list can mark them. */
    fun pendingIds(): Flow<Set<String>>

    /** Throw away an unsent write. */
    suspend fun discardPending(id: String)
}

@Singleton
class DefaultMembersRepository @Inject constructor(
    private val apiClient: ApiClient,
    private val members: SyncedMemberDao,
    private val cursors: SyncCursorDao,
    private val writes: WriteQueue,
    private val json: Json,
) : MembersRepository {

    /**
     * The mirror with the unsent writes laid over it.
     *
     * Not written into `synced_members` directly, for two reasons that both
     * end badly: the sweep after a re-bootstrap would delete a creation that
     * has never been sent, and an edit written into the mirror is
     * indistinguishable from one the server has confirmed — so a failed send
     * would leave a lie on the device with nothing left to retry it.
     */
    override fun stream(query: String): Flow<List<Member>> = combine(
        members.search(query),
        writes.pending(MemberSyncCollection.COLLECTION),
    ) { rows, pending ->
        val drafts = pending.mapNotNull { write -> draftOf(write)?.let { write.recordId to it } }
            .toMap()

        val mirrored = rows.map { row ->
            drafts[row.id]?.let { row.toDomain().withDraft(it) } ?: row.toDomain()
        }
        // A creation the server has never seen has no mirror row to sit on, so
        // it is built from the draft alone. Filtered here rather than in SQL
        // because it is not in the table the query runs against.
        val mirroredIds = rows.mapTo(mutableSetOf()) { it.id }
        val created = pending
            .filter { it.op == PendingWrite.OP_CREATE && it.recordId !in mirroredIds }
            .mapNotNull { write -> drafts[write.recordId]?.asNewMember(write.recordId) }
            .filter { it.matches(query) }

        (created + mirrored).sortedBy { foldForSearch("${it.lastName} ${it.firstName}") }
    }

    override fun count(): Flow<Int> = members.countStream()

    override fun hasSynced(): Flow<Boolean> =
        cursors.bootstrapCompleteStream(MemberSyncCollection.COLLECTION)

    /**
     * One member, with an unsent write laid over it — the same overlay
     * [stream] applies, and for the same reason.
     *
     * Without it the detail screen reads the mirror alone, so a member edited
     * without a connection would show the *old* values the moment the form
     * closed: the edit is in the queue, the mirror has not heard of it, and to
     * whoever typed it that is indistinguishable from a save that failed.
     */
    /**
     * One member, with an unsent write laid over it — the same overlay
     * [stream] applies, and for the same reason.
     *
     * Without it the detail screen reads the mirror alone, so a member edited
     * without a connection would show the *old* values the moment the form
     * closed: the edit is in the queue, the mirror has not heard of it, and to
     * whoever typed it that is indistinguishable from a save that failed.
     */
    override fun byIdStream(id: String): Flow<Member?> = combine(
        members.byIdStream(id),
        writes.pendingFor(MemberSyncCollection.COLLECTION, id),
    ) { row, queued ->
        val draft = queued?.let(::draftOf)
        when {
            row != null && draft != null -> row.toDomain().withDraft(draft)
            row != null -> row.toDomain()
            // Created on this device and never sent: there is no mirror row to
            // sit on, and the detail screen still has to open on it.
            draft != null -> draft.asNewMember(id)
            else -> null
        }
    }

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

    override suspend fun save(id: String?, draft: MemberDraft): String {
        val recordId = id ?: UUID.randomUUID().toString()
        val creating = id == null
        writes.enqueue(
            entity = MemberSyncCollection.COLLECTION,
            recordId = recordId,
            op = if (creating) PendingWrite.OP_CREATE else PendingWrite.OP_UPDATE,
            payloadJson = if (creating) {
                json.encodeToString(draft.toCreatePayload(recordId))
            } else {
                json.encodeToString(draft.toUpdatePayload())
            },
            label = "${draft.firstName} ${draft.lastName}".trim(),
        )
        return recordId
    }

    override fun pendingIds(): Flow<Set<String>> =
        writes.pending(MemberSyncCollection.COLLECTION)
            .map { writes -> writes.mapTo(mutableSetOf()) { it.recordId } }

    override suspend fun discardPending(id: String) =
        writes.discard(MemberSyncCollection.COLLECTION, id)

    /**
     * The draft inside a queued write.
     *
     * Null when the payload will not decode, which can only happen if a build
     * changed the shape under a row that was already queued. Returning null
     * leaves the mirror's version showing rather than blanking the member; the
     * queue drops the row on its own when the server refuses it.
     */
    private fun draftOf(write: PendingWrite): MemberDraft? = runCatching {
        if (write.op == PendingWrite.OP_CREATE) {
            json.decodeFromString<MemberCreatePayload>(write.payloadJson).toDraft()
        } else {
            json.decodeFromString<MemberUpdatePayload>(write.payloadJson).toDraft()
        }
    }.getOrNull()
}

private fun Member.withDraft(draft: MemberDraft) = copy(
    firstName = draft.firstName,
    lastName = draft.lastName,
    email = draft.email,
    phone = draft.phone,
    mobile = draft.mobile,
    birthday = draft.birthday,
    gender = draft.gender,
    street = draft.street,
    zipCode = draft.zipCode,
    city = draft.city,
    status = MemberStatus.fromApi(draft.status),
    category = draft.category,
    joinedAt = draft.joinedAt ?: joinedAt,
)

/**
 * A member that exists only on this device so far.
 *
 * The member number is empty because the server allocates it — the list shows
 * the "not sent" marker in its place, which is truer than inventing one.
 */
private fun MemberDraft.asNewMember(id: String) = Member(
    id = id,
    memberNumber = "",
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
    joinedAt = joinedAt.orEmpty(),
    leftAt = null,
    iban = null,
)

/** The same folding the mirror's `searchKey` uses, so both lists filter alike. */
private fun Member.matches(query: String): Boolean {
    if (query.isBlank()) return true
    val needle = foldForSearch(query)
    return foldForSearch(listOfNotNull(firstName, lastName, email).joinToString(" "))
        .contains(needle)
}

internal fun MemberCreatePayload.toDraft() = MemberDraft(
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
    status = status,
    category = category,
    joinedAt = joinedAt,
)

internal fun MemberUpdatePayload.toDraft() = MemberDraft(
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
    status = status,
    category = category,
    joinedAt = joinedAt,
)

@Module
@InstallIn(SingletonComponent::class)
abstract class MembersModule {
    @Binds
    abstract fun bindMembersRepository(impl: DefaultMembersRepository): MembersRepository
}
