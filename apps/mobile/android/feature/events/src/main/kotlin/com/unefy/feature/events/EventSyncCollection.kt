package com.unefy.feature.events

import com.unefy.core.database.SyncedEvent
import com.unefy.core.database.SyncedEventDao
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
 * Turns a page of `/api/v1/sync/events` into rows in the local mirror.
 *
 * Decoded with the same [EventDto] the list endpoint uses; the sync payload is
 * the bare row, so the DTO's defaults absorb what is absent there —
 * `is_registered` (missing entirely), `registered_count` (0) and
 * `competition_name` (null). Those never reach the mirror: [toRow] copies only
 * the mirrored columns, and the screens get the rest from the online overlay.
 */
@Singleton
class EventSyncCollection @Inject constructor(
    private val dao: SyncedEventDao,
    private val json: Json,
) : SyncCollection {

    override val name = COLLECTION

    override suspend fun apply(
        changed: List<JsonElement>,
        deleted: List<String>,
        generation: Long,
    ) {
        dao.upsert(
            changed.map { json.decodeFromJsonElement(EventDto.serializer(), it).toRow(generation) },
        )
        dao.deleteByIds(deleted)
    }

    override suspend fun sweep(generation: Long) = dao.sweep(generation)

    override suspend fun clear() = dao.deleteAll()

    companion object {
        /** Sync path segment and `entity` value on the change stream. */
        const val COLLECTION = "events"
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class EventSyncModule {
    @Binds
    @IntoSet
    abstract fun bindEventSyncCollection(impl: EventSyncCollection): SyncCollection
}

/** The DTO as a mirror row — only the fields the mirror carries. */
internal fun EventDto.toRow(generation: Long) = SyncedEvent(
    id = id,
    title = title,
    description = description,
    eventType = eventType,
    location = location,
    startsAt = startsAt,
    endsAt = endsAt,
    allDay = allDay,
    registrationRequired = registrationRequired,
    registrationDeadline = registrationDeadline,
    maxParticipants = maxParticipants,
    status = status,
    generation = generation,
)
