package com.unefy.feature.members

import com.unefy.core.database.SyncedMember
import com.unefy.core.database.SyncedMemberDao
import com.unefy.core.sync.SyncCollection
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import dagger.multibindings.IntoSet
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement

/**
 * Turns a page of `/api/v1/sync/members` into rows in the local mirror.
 *
 * The decoding lives here rather than in `core:sync` because the shape of a member
 * is this feature's business: [MemberDto] is the DTO already maintained against
 * the OpenAPI spec, and reusing it means the mirror and the rest of the app cannot
 * disagree about what the backend sends.
 */
@Singleton
class MemberSyncCollection @Inject constructor(
    private val dao: SyncedMemberDao,
    private val json: Json,
) : SyncCollection {

    override val name = COLLECTION

    override suspend fun apply(
        changed: List<JsonElement>,
        deleted: List<String>,
        generation: Long,
    ) {
        // Upsert, never insert: the server's pages are a superset of what changed,
        // so the same member legitimately arrives twice — once at the end of one
        // page and again at the start of the next after a concurrent edit.
        dao.upsert(changed.map { json.decodeFromJsonElement(MemberDto.serializer(), it).toRow(generation) })
        dao.deleteByIds(deleted)
    }

    override suspend fun sweep(generation: Long) = dao.sweep(generation)

    override suspend fun clear() = dao.deleteAll()

    companion object {
        /**
         * The collection name, which is also the sync path segment and the `entity`
         * value on the change stream. Plural, matching the backend registry.
         */
        const val COLLECTION = "members"
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class MemberSyncModule {
    @Binds
    @IntoSet
    abstract fun bindMemberSyncCollection(impl: MemberSyncCollection): SyncCollection
}

/**
 * The DTO as a mirror row.
 *
 * `iban` is dropped on purpose and is the one field the mirror does not carry —
 * see [SyncedMember]. The rest is a straight copy; `searchKey` and `sortKey` are
 * derived by the entity itself.
 */
internal fun MemberDto.toRow(generation: Long) = SyncedMember(
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
    status = status,
    category = category,
    joinedAt = joinedAt,
    leftAt = leftAt,
    generation = generation,
)
