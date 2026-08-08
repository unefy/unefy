package com.unefy.feature.members

import com.unefy.core.database.PendingWrite
import com.unefy.core.database.SyncCursorDao
import com.unefy.core.database.SyncedMember
import com.unefy.core.database.SyncedMemberDao
import com.unefy.core.model.Member
import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiEndpoints
import com.unefy.core.network.ApiResult
import com.unefy.core.sync.PendingWriteHandler
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import dagger.multibindings.IntoSet
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * The fields of a member this app lets somebody change.
 *
 * Bank details are deliberately absent, and their absence is load-bearing: the
 * mirror does not hold them (see `SyncedMember`), so a form that offered them
 * would have to fetch them over the network, keep them in memory and send them
 * back — turning every edit into an online-only operation and putting an IBAN
 * on a screen in a clubhouse. They stay with the web app.
 *
 * `memberNumber` is absent for a different reason: the server allocates it.
 */
data class MemberDraft(
    val firstName: String = "",
    val lastName: String = "",
    val email: String? = null,
    val phone: String? = null,
    val mobile: String? = null,
    val birthday: String? = null,
    val gender: String? = null,
    val street: String? = null,
    val zipCode: String? = null,
    val city: String? = null,
    val status: String = "active",
    val category: String? = null,
    val joinedAt: String? = null,
) {
    /** Both names present. The server enforces it too; this keeps the form honest. */
    val isComplete: Boolean
        get() = firstName.isNotBlank() && lastName.isNotBlank()

    /** What the header shows while the name is being changed. */
    val displayName: String
        get() = "$firstName $lastName".trim()
}

internal fun Member.toDraft() = MemberDraft(
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
    status = status.apiValue,
    category = category,
    joinedAt = joinedAt.takeIf { it.isNotBlank() },
)

/**
 * A queued creation, as the server will receive it.
 *
 * No defaults anywhere, so every field is serialised — including the null ones.
 * A field the user cleared has to travel as an explicit `null`, or clearing an
 * email would be indistinguishable from not mentioning it.
 */
@Serializable
internal data class MemberCreatePayload(
    val id: String,
    @SerialName("first_name") val firstName: String,
    @SerialName("last_name") val lastName: String,
    val email: String?,
    val phone: String?,
    val mobile: String?,
    val birthday: String?,
    val gender: String?,
    val street: String?,
    @SerialName("zip_code") val zipCode: String?,
    val city: String?,
    val status: String,
    val category: String?,
    @SerialName("joined_at") val joinedAt: String?,
)

/** The same fields without the id, which a PATCH must not carry. */
@Serializable
internal data class MemberUpdatePayload(
    @SerialName("first_name") val firstName: String,
    @SerialName("last_name") val lastName: String,
    val email: String?,
    val phone: String?,
    val mobile: String?,
    val birthday: String?,
    val gender: String?,
    val street: String?,
    @SerialName("zip_code") val zipCode: String?,
    val city: String?,
    val status: String,
    val category: String?,
    @SerialName("joined_at") val joinedAt: String?,
)

internal fun MemberDraft.toCreatePayload(id: String) = MemberCreatePayload(
    id = id,
    firstName = firstName.trim(),
    lastName = lastName.trim(),
    email = email.orNullIfBlank(),
    phone = phone.orNullIfBlank(),
    mobile = mobile.orNullIfBlank(),
    birthday = birthday.orNullIfBlank(),
    gender = gender.orNullIfBlank(),
    street = street.orNullIfBlank(),
    zipCode = zipCode.orNullIfBlank(),
    city = city.orNullIfBlank(),
    status = status,
    category = category.orNullIfBlank(),
    joinedAt = joinedAt.orNullIfBlank(),
)

internal fun MemberDraft.toUpdatePayload() = MemberUpdatePayload(
    firstName = firstName.trim(),
    lastName = lastName.trim(),
    email = email.orNullIfBlank(),
    phone = phone.orNullIfBlank(),
    mobile = mobile.orNullIfBlank(),
    birthday = birthday.orNullIfBlank(),
    gender = gender.orNullIfBlank(),
    street = street.orNullIfBlank(),
    zipCode = zipCode.orNullIfBlank(),
    city = city.orNullIfBlank(),
    status = status,
    category = category.orNullIfBlank(),
    joinedAt = joinedAt.orNullIfBlank(),
)

/**
 * A blank field means "no value", not the empty string.
 *
 * Without this an untouched optional field arrives as `""`, which passes
 * validation and leaves a member with an email address of nothing — which then
 * sorts, exports and mail-merges as a real value.
 */
private fun String?.orNullIfBlank(): String? = this?.trim()?.takeIf { it.isNotEmpty() }

/**
 * Sends queued member writes.
 *
 * On success the server's own row goes straight into the mirror rather than
 * waiting for the next sync: the queue row is about to be deleted, and without
 * this the member would vanish from the list for as long as it takes the next
 * delta to arrive — which reads exactly like a save that failed.
 */
@Singleton
class MemberWriteHandler @Inject constructor(
    private val apiClient: ApiClient,
    private val members: SyncedMemberDao,
    private val cursors: SyncCursorDao,
    private val json: Json,
) : PendingWriteHandler {

    override val entity = MemberSyncCollection.COLLECTION

    override suspend fun send(write: PendingWrite): ApiResult<Unit> {
        val result = when (write.op) {
            PendingWrite.OP_CREATE -> apiClient.post<MemberDto>(
                ApiEndpoints.MEMBERS,
                json.decodeFromString<MemberCreatePayload>(write.payloadJson),
            )
            else -> apiClient.patch<MemberDto>(
                ApiEndpoints.member(write.recordId),
                json.decodeFromString<MemberUpdatePayload>(write.payloadJson),
                // No `If-Match`. A queued edit may be hours old, and a
                // precondition would fail on anything the club changed in the
                // meantime — turning "saved while offline" into a conflict the
                // person who typed it is no longer around to resolve.
                // Last-write-wins is the documented mobile strategy.
            )
        }

        return when (result) {
            is ApiResult.Success -> {
                members.upsert(listOf(result.data.toSynced(currentGeneration())))
                ApiResult.Success(Unit)
            }
            is ApiResult.Failure -> ApiResult.Failure(result.error)
        }
    }

    /**
     * The generation the current sync is stamping.
     *
     * Carried over rather than invented: a lower one and the next sweep drops
     * this member, a higher one and it survives a sweep it should not.
     */
    private suspend fun currentGeneration(): Long =
        cursors.get(MemberSyncCollection.COLLECTION)?.generation ?: 1L
}

internal fun MemberDto.toSynced(generation: Long) = SyncedMember(
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
    status = status,
    category = category,
    joinedAt = joinedAt,
    leftAt = leftAt,
    generation = generation,
)

@Module
@InstallIn(SingletonComponent::class)
abstract class MemberWriteModule {
    @Binds
    @IntoSet
    abstract fun bindMemberWriteHandler(impl: MemberWriteHandler): PendingWriteHandler
}
