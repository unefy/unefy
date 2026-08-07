package com.unefy.feature.scoring

import com.unefy.core.database.SyncedEntry
import com.unefy.core.database.SyncedEntryDao
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
 * Turns a page of `GET /api/v1/sync/entries` into rows in the club-wide mirror.
 *
 * The collection is board-only on the server. A plain member's device still
 * registers this — the coordinator asks the manifest which collections the
 * account may sync, so an unentitled one is never requested and the table stays
 * empty rather than erroring on every drain.
 */
@Singleton
class EntrySyncCollection @Inject constructor(
    private val dao: SyncedEntryDao,
    private val json: Json,
) : SyncCollection {

    override val name = COLLECTION

    override suspend fun apply(
        changed: List<JsonElement>,
        deleted: List<String>,
        generation: Long,
    ) {
        dao.upsert(
            changed.map { json.decodeFromJsonElement(EntryDto.serializer(), it).toRow(json, generation) },
        )
        dao.deleteByIds(deleted)
    }

    override suspend fun sweep(generation: Long) = dao.sweep(generation)

    override suspend fun clear() = dao.deleteAll()

    companion object {
        /** Sync path segment and `entity` value on the change stream. */
        const val COLLECTION = "entries"
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class EntrySyncModule {
    @Binds
    @IntoSet
    abstract fun bindEntrySyncCollection(impl: EntrySyncCollection): SyncCollection
}

/**
 * The DTO as a mirror row.
 *
 * The shots are re-encoded rather than carried over as the raw `details` object:
 * the row stores the same shape `cached_my_entries` does, so one mapping back to
 * [ShotSeries] serves both tables.
 */
internal fun EntryDto.toRow(json: Json, generation: Long) = SyncedEntry(
    id = id,
    sessionId = sessionId,
    memberId = memberId,
    scoreValue = scoreValue,
    scoreUnit = scoreUnit,
    discipline = discipline,
    targetType = details?.targetType,
    caliberMm = details?.caliberMm,
    shotsJson = details?.shots?.let { json.encodeToString(it) },
    innerTens = details?.innerTens,
    groupingMm = details?.groupingMm,
    source = source,
    recordedAt = recordedAt,
    notes = notes,
    generation = generation,
)
