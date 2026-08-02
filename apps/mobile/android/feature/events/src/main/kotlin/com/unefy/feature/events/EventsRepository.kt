package com.unefy.feature.events

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
)

interface EventsRepository {
    /**
     * One slice of the calendar.
     *
     * The time window and the order are the backend's job, not a filter applied
     * to whatever the first page happened to contain. Sorted ascending and
     * unfiltered — the old behaviour — page one of a club with a few years of
     * history is its oldest events, and "kommende Termine" stays empty until
     * every past one has been paged through.
     */
    suspend fun list(
        page: Int = 1,
        perPage: Int = 50,
        startsAfter: String? = null,
        startsBefore: String? = null,
        newestFirst: Boolean = false,
    ): ApiResult<List<Event>>

    /** Self-service: registers the caller, never someone else. */
    suspend fun register(eventId: String): ApiResult<Unit>

    suspend fun unregister(eventId: String): ApiResult<Unit>
}

@Singleton
class DefaultEventsRepository @Inject constructor(
    private val apiClient: ApiClient,
) : EventsRepository {
    override suspend fun list(
        page: Int,
        perPage: Int,
        startsAfter: String?,
        startsBefore: String?,
        newestFirst: Boolean,
    ): ApiResult<List<Event>> = apiClient
        .get<List<EventDto>>(ApiEndpoints.EVENTS) {
            parameter("page", page)
            parameter("per_page", perPage)
            startsAfter?.let { parameter("starts_after", it) }
            startsBefore?.let { parameter("starts_before", it) }
            parameter("sort_order", if (newestFirst) "desc" else "asc")
        }
        .map { dtos -> dtos.map(EventDto::toDomain) }

    override suspend fun register(eventId: String): ApiResult<Unit> = apiClient
        .post<RegistrationDto>(ApiEndpoints.eventSelfRegistration(eventId))
        .map { }

    override suspend fun unregister(eventId: String): ApiResult<Unit> =
        apiClient.deleteNoContent(ApiEndpoints.eventSelfRegistration(eventId))
}

@Serializable
internal data class RegistrationDto(val id: String)

@Module
@InstallIn(SingletonComponent::class)
abstract class EventsModule {
    @Binds
    abstract fun bindEventsRepository(impl: DefaultEventsRepository): EventsRepository
}
