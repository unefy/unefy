package com.unefy.feature.events

import com.unefy.core.database.PendingWrite
import com.unefy.core.database.SyncCursorDao
import com.unefy.core.database.SyncedEvent
import com.unefy.core.database.SyncedEventDao
import com.unefy.core.model.Event
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
 * The fields of an event this app lets somebody change.
 *
 * The competition link is absent: an event tied to a competition session has
 * its type forced and its session validated server-side, and offering that here
 * would mean shipping the whole competition picker into a form whose job is
 * "club evening, Friday, seven". Linked events are created from the competition
 * side, in the web app.
 */
data class EventDraft(
    val title: String = "",
    val description: String? = null,
    val eventType: String = "other",
    val location: String? = null,
    /** ISO-8601 instant. The one field an event cannot do without. */
    val startsAt: String? = null,
    val endsAt: String? = null,
    val allDay: Boolean = false,
    val registrationRequired: Boolean = false,
    val maxParticipants: Int? = null,
) {
    val isComplete: Boolean
        get() = title.isNotBlank() && startsAt != null && !endsBeforeItStarts

    /**
     * The server refuses this too, with a 422 the queue would surface hours
     * later. Catching it in the form is the difference between a typo and a
     * mystery.
     */
    val endsBeforeItStarts: Boolean
        get() = startsAt != null && endsAt != null && endsAt < startsAt
}

internal fun Event.toDraft() = EventDraft(
    title = title,
    description = description,
    eventType = type ?: "other",
    location = location,
    startsAt = startsAt.takeIf { it.isNotBlank() },
    endsAt = endsAt,
    allDay = allDay,
    registrationRequired = registrationRequired,
    maxParticipants = maxParticipants,
)

@Serializable
internal data class EventCreatePayload(
    val id: String,
    val title: String,
    val description: String?,
    @SerialName("event_type") val eventType: String,
    val location: String?,
    @SerialName("starts_at") val startsAt: String,
    @SerialName("ends_at") val endsAt: String?,
    @SerialName("all_day") val allDay: Boolean,
    @SerialName("registration_required") val registrationRequired: Boolean,
    @SerialName("max_participants") val maxParticipants: Int?,
)

@Serializable
internal data class EventUpdatePayload(
    val title: String,
    val description: String?,
    @SerialName("event_type") val eventType: String,
    val location: String?,
    @SerialName("starts_at") val startsAt: String,
    @SerialName("ends_at") val endsAt: String?,
    @SerialName("all_day") val allDay: Boolean,
    @SerialName("registration_required") val registrationRequired: Boolean,
    @SerialName("max_participants") val maxParticipants: Int?,
)

/** Null only if the draft is incomplete, which the form prevents. */
internal fun EventDraft.toCreatePayload(id: String): EventCreatePayload? = EventCreatePayload(
    id = id,
    title = title.trim(),
    description = description.orNullIfBlank(),
    eventType = eventType,
    location = location.orNullIfBlank(),
    startsAt = startsAt ?: return null,
    endsAt = endsAt,
    allDay = allDay,
    registrationRequired = registrationRequired,
    maxParticipants = maxParticipants,
)

internal fun EventDraft.toUpdatePayload(): EventUpdatePayload? = EventUpdatePayload(
    title = title.trim(),
    description = description.orNullIfBlank(),
    eventType = eventType,
    location = location.orNullIfBlank(),
    startsAt = startsAt ?: return null,
    endsAt = endsAt,
    allDay = allDay,
    registrationRequired = registrationRequired,
    maxParticipants = maxParticipants,
)

private fun String?.orNullIfBlank(): String? = this?.trim()?.takeIf { it.isNotEmpty() }

/** Sends queued event writes. The member handler's twin — see its notes. */
@Singleton
class EventWriteHandler @Inject constructor(
    private val apiClient: ApiClient,
    private val events: SyncedEventDao,
    private val cursors: SyncCursorDao,
    private val json: Json,
) : PendingWriteHandler {

    override val entity = EventSyncCollection.COLLECTION

    override suspend fun send(write: PendingWrite): ApiResult<Unit> {
        val result = when (write.op) {
            PendingWrite.OP_CREATE -> apiClient.post<EventDto>(
                ApiEndpoints.EVENTS,
                json.decodeFromString<EventCreatePayload>(write.payloadJson),
            )
            else -> apiClient.patch<EventDto>(
                ApiEndpoints.event(write.recordId),
                json.decodeFromString<EventUpdatePayload>(write.payloadJson),
            )
        }

        return when (result) {
            is ApiResult.Success -> {
                events.upsert(listOf(result.data.toSynced(currentGeneration())))
                ApiResult.Success(Unit)
            }
            is ApiResult.Failure -> ApiResult.Failure(result.error)
        }
    }

    private suspend fun currentGeneration(): Long =
        cursors.get(EventSyncCollection.COLLECTION)?.generation ?: 1L
}

internal fun EventDto.toSynced(generation: Long) = SyncedEvent(
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

@Module
@InstallIn(SingletonComponent::class)
abstract class EventWriteModule {
    @Binds
    @IntoSet
    abstract fun bindEventWriteHandler(impl: EventWriteHandler): PendingWriteHandler
}
