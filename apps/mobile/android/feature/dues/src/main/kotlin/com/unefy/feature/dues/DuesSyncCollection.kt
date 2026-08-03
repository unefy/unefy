package com.unefy.feature.dues

import com.unefy.core.database.SyncedDue
import com.unefy.core.database.SyncedDueDao
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
 * Turns a page of `/api/v1/sync/dues` into rows in the local mirror.
 *
 * Board-only in effect: the server answers 403 for a plain member and the
 * coordinator latches that as NotPermitted, so this collection simply never
 * fills on a member's phone. `member_name` is deliberately dropped by [toRow] —
 * the sync payload always carries null there, and the screens join the name
 * from the member mirror instead.
 */
@Singleton
class DuesSyncCollection @Inject constructor(
    private val dao: SyncedDueDao,
    private val json: Json,
) : SyncCollection {

    override val name = COLLECTION

    override suspend fun apply(
        changed: List<JsonElement>,
        deleted: List<String>,
        generation: Long,
    ) {
        dao.upsert(
            changed.map { json.decodeFromJsonElement(DuesDto.serializer(), it).toRow(generation) },
        )
        dao.deleteByIds(deleted)
    }

    override suspend fun sweep(generation: Long) = dao.sweep(generation)

    override suspend fun clear() = dao.deleteAll()

    companion object {
        /** Sync path segment and `entity` value on the change stream. */
        const val COLLECTION = "dues"
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class DuesSyncModule {
    @Binds
    @IntoSet
    abstract fun bindDuesSyncCollection(impl: DuesSyncCollection): SyncCollection
}

/** The DTO as a mirror row — `memberName` comes from the join, not from here. */
internal fun DuesDto.toRow(generation: Long) = SyncedDue(
    id = id,
    memberId = memberId,
    feeName = feeName,
    amount = amount,
    dueDate = dueDate,
    status = status,
    paidAt = paidAt,
    generation = generation,
)
