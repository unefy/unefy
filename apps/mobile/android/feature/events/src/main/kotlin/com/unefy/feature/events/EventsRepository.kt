package com.unefy.feature.events

import com.unefy.core.database.SyncCursorDao
import com.unefy.core.database.SyncedEvent
import com.unefy.core.database.SyncedEventDao
import com.unefy.core.model.Event
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

@Serializable
internal data class EventDto(
    val id: String,
    val title: String,
    val description: String? = null,
    @SerialName("event_type") val eventType: String? = null,
    val location: String? = null,
    @SerialName("starts_at") val startsAt: String = "",
    @SerialName("ends_at") val endsAt: String? = null,
    @SerialName("all_day") val allDay: Boolean = false,
    @SerialName("registration_required") val registrationRequired: Boolean = false,
    @SerialName("registration_deadline") val registrationDeadline: String? = null,
    @SerialName("registered_count") val registeredCount: Int = 0,
    @SerialName("max_participants") val maxParticipants: Int? = null,
    val status: String? = null,
    @SerialName("is_registered") val isRegistered: Boolean = false,
    @SerialName("competition_name") val competitionName: String? = null,
)

internal fun EventDto.toDomain() = Event(
    id = id,
    title = title,
    description = description,
    type = eventType,
    location = location,
    startsAt = startsAt,
    endsAt = endsAt,
    allDay = allDay,
    registrationRequired = registrationRequired,
    registrationDeadline = registrationDeadline,
    registeredCount = registeredCount,
    maxParticipants = maxParticipants,
    status = status,
    isRegistered = isRegistered,
    competitionName = competitionName,
)

/**
 * A mirror row as the domain model.
 *
 * The three enrichment fields stay at their defaults — they are not a gap but
 * the mirror's design: `is_registered`, `registered_count` and
 * `competition_name` are list-endpoint enrichment the sync payload never
 * carries, and the screen overlays them from [EventsRepository.overlay] when it
 * is online. Offline they are simply not shown, rather than shown wrong.
 */
internal fun SyncedEvent.toDomain() = Event(
    id = id,
    title = title,
    description = description,
    type = eventType,
    location = location,
    startsAt = startsAt,
    endsAt = endsAt,
    allDay = allDay,
    registrationRequired = registrationRequired,
    registrationDeadline = registrationDeadline,
    registeredCount = 0,
    maxParticipants = maxParticipants,
    status = status,
    isRegistered = false,
    competitionName = null,
)

/** The caller-specific and derived fields of one event, fetched online. */
data class EventOverlay(
    val isRegistered: Boolean,
    val registeredCount: Int,
    val competitionName: String?,
)

interface EventsRepository {
    /** The calendar, from the local mirror, ascending by start. */
    fun stream(): Flow<List<Event>>

    /** Whether the mirror holds the whole collection — see MembersRepository. */
    fun hasSynced(): Flow<Boolean>

    /**
     * The enrichment the mirror deliberately lacks, keyed by event id.
     *
     * One request against the list endpoint, newest first, at the server's
     * per-page maximum. Events beyond that window get no entry — the screen
     * then hides the capacity pill, exactly as it does offline. Acceptable:
     * the window covers everything upcoming plus the recent past, and past
     * events have no registration control anyway.
     */
    suspend fun overlay(): ApiResult<Map<String, EventOverlay>>

    /** Self-service: registers the caller, never someone else. */
    suspend fun register(eventId: String): ApiResult<Unit>

    suspend fun unregister(eventId: String): ApiResult<Unit>
}

@Singleton
class DefaultEventsRepository @Inject constructor(
    private val apiClient: ApiClient,
    private val events: SyncedEventDao,
    private val cursors: SyncCursorDao,
) : EventsRepository {

    override fun stream(): Flow<List<Event>> =
        events.all().map { rows -> rows.map(SyncedEvent::toDomain) }

    override fun hasSynced(): Flow<Boolean> =
        cursors.bootstrapCompleteStream(EventSyncCollection.COLLECTION)

    override suspend fun overlay(): ApiResult<Map<String, EventOverlay>> = apiClient
        .get<List<EventDto>>(ApiEndpoints.EVENTS) {
            parameter("page", 1)
            parameter("per_page", OVERLAY_WINDOW)
            parameter("sort_order", "desc")
        }
        .map { dtos ->
            dtos.associate {
                it.id to EventOverlay(it.isRegistered, it.registeredCount, it.competitionName)
            }
        }

    override suspend fun register(eventId: String): ApiResult<Unit> = apiClient
        .post<RegistrationDto>(ApiEndpoints.eventSelfRegistration(eventId))
        .map { }

    override suspend fun unregister(eventId: String): ApiResult<Unit> =
        apiClient.deleteNoContent(ApiEndpoints.eventSelfRegistration(eventId))

    private companion object {
        /** The server's `per_page` maximum (`le=100` on the list route). */
        const val OVERLAY_WINDOW = 100
    }
}

@Serializable
internal data class RegistrationDto(val id: String)

@Module
@InstallIn(SingletonComponent::class)
abstract class EventsModule {
    @Binds
    abstract fun bindEventsRepository(impl: DefaultEventsRepository): EventsRepository
}
