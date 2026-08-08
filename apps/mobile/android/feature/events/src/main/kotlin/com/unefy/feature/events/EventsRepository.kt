package com.unefy.feature.events

import com.unefy.core.database.PendingWrite
import com.unefy.core.database.SyncCursorDao
import com.unefy.core.database.SyncedEvent
import com.unefy.core.database.SyncedEventDao
import com.unefy.core.database.SyncedMemberDao
import com.unefy.core.model.Event
import com.unefy.core.model.EventAttendanceSession
import com.unefy.core.model.EventDetail
import com.unefy.core.model.EventRegistration
import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiEndpoints
import com.unefy.core.network.ApiResult
import com.unefy.core.network.map
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import io.ktor.client.request.parameter
import com.unefy.core.sync.WriteQueue
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

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

/**
 * The single-event response: the same row as [EventDto] plus the merged-in
 * `registrations`. A separate DTO rather than a nullable field on [EventDto]
 * because the list endpoint never sends the array, and "absent" and "empty"
 * must not collapse into the same value on the detail screen.
 */
@Serializable
internal data class EventDetailDto(
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
    val registrations: List<EventRegistrationDto> = emptyList(),
    // Board only — the backend sends an empty array to plain members.
    @SerialName("attendance_sessions")
    val attendanceSessions: List<EventAttendanceSessionDto> = emptyList(),
)

/** An attendance session hung off the event, as the detail embeds it. */
@Serializable
internal data class EventAttendanceSessionDto(
    val id: String,
    val title: String = "",
    val status: String = "open",
    @SerialName("record_count") val recordCount: Int = 0,
)

internal fun EventAttendanceSessionDto.toDomain() = EventAttendanceSession(
    id = id,
    title = title,
    status = status,
    recordCount = recordCount,
)

@Serializable
internal data class EventRegistrationDto(
    val id: String,
    @SerialName("member_id") val memberId: String = "",
    @SerialName("member_name") val memberName: String? = null,
    val status: String = "registered",
    val note: String? = null,
)

internal fun EventDetailDto.toDomain() = EventDetail(
    event = Event(
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
    ),
    registrations = registrations.map {
        EventRegistration(
            id = it.id,
            memberId = it.memberId,
            memberName = it.memberName,
            status = it.status,
            note = it.note,
        )
    },
    attendanceSessions = attendanceSessions.map(EventAttendanceSessionDto::toDomain),
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

    /** One event from the mirror, live — the offline backbone of the detail. */
    fun byIdStream(id: String): Flow<Event?>

    /**
     * The single event with its registrations, online. The detail screen lays
     * this over the mirrored row: enrichment and the list of names are the two
     * things the sync payload never carries.
     */
    suspend fun detail(id: String): ApiResult<EventDetail>

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

    /**
     * Board-level: the event's open attendance session — found or freshly
     * opened by the backend, prefilled from the event. Idempotent; a second
     * call returns the same session.
     */
    suspend fun openAttendanceSession(eventId: String): ApiResult<EventAttendanceSession>

    /** Self-service: registers the caller, never someone else. */
    suspend fun register(eventId: String): ApiResult<Unit>

    suspend fun unregister(eventId: String): ApiResult<Unit>

    /**
     * Board-level: registers another member; a full event waitlists them.
     * Returns the new registration's id, so the caller can show the row
     * without waiting for a re-fetch.
     */
    suspend fun registerMember(eventId: String, memberId: String): ApiResult<String>

    /** Board-level: removes a registration; the server promotes the waitlist. */
    suspend fun removeRegistration(eventId: String, registrationId: String): ApiResult<Unit>

    /**
     * The pick list for the board's add sheet. The member mirror answers once
     * its bootstrap is through — instant and offline; until then the list
     * endpoint fills in, exactly like the attendance pick list.
     */
    suspend fun memberOptions(search: String?): ApiResult<List<MemberOption>>

    /**
     * Save an event into the local queue. [id] null means create; returns the
     * record's id. Cannot fail — see `MembersRepository.save`.
     */
    suspend fun save(id: String?, draft: EventDraft): String

    /** The ids with an unsent write, so a list can mark them. */
    fun pendingIds(): Flow<Set<String>>

}

/** One row of the add sheet — who could be put on the event. */
data class MemberOption(
    val id: String,
    val memberNumber: String,
    val name: String,
)

@Singleton
class DefaultEventsRepository @Inject constructor(
    private val apiClient: ApiClient,
    private val events: SyncedEventDao,
    private val members: SyncedMemberDao,
    private val cursors: SyncCursorDao,
    private val writes: WriteQueue,
    private val json: Json,
) : EventsRepository {

    /** The mirror with unsent writes laid over it — see `DefaultMembersRepository`. */
    override fun stream(): Flow<List<Event>> = combine(
        events.all(),
        writes.pending(EventSyncCollection.COLLECTION),
    ) { rows, pending ->
        val drafts = pending.mapNotNull { write -> draftOf(write)?.let { write.recordId to it } }
            .toMap()
        val mirrored = rows.map { row ->
            drafts[row.id]?.let { row.toDomain().withDraft(it) } ?: row.toDomain()
        }
        val mirroredIds = rows.mapTo(mutableSetOf()) { it.id }
        val created = pending
            .filter { it.op == PendingWrite.OP_CREATE && it.recordId !in mirroredIds }
            .mapNotNull { write -> drafts[write.recordId]?.asNewEvent(write.recordId) }

        // Ascending by start, as the DAO returns them — the ViewModel splits
        // upcoming from past on that order and would mis-split without it.
        (created + mirrored).sortedWith(compareBy({ it.startsAt }, { it.title }))
    }

    override fun hasSynced(): Flow<Boolean> =
        cursors.bootstrapCompleteStream(EventSyncCollection.COLLECTION)

    override fun byIdStream(id: String): Flow<Event?> = combine(
        events.byIdStream(id),
        writes.pendingFor(EventSyncCollection.COLLECTION, id),
    ) { row, queued ->
        val draft = queued?.let(::draftOf)
        when {
            row != null && draft != null -> row.toDomain().withDraft(draft)
            row != null -> row.toDomain()
            // Created on this device and not sent yet: the detail screen has to
            // open on it, or tapping the row one has just added does nothing.
            draft != null -> draft.asNewEvent(id)
            else -> null
        }
    }

    override suspend fun detail(id: String): ApiResult<EventDetail> = apiClient
        .get<EventDetailDto>(ApiEndpoints.event(id))
        .map(EventDetailDto::toDomain)

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

    override suspend fun openAttendanceSession(
        eventId: String,
    ): ApiResult<EventAttendanceSession> = apiClient
        .post<EventAttendanceSessionDto>("${ApiEndpoints.event(eventId)}/attendance-session")
        .map(EventAttendanceSessionDto::toDomain)

    override suspend fun register(eventId: String): ApiResult<Unit> = apiClient
        .post<RegistrationDto>(ApiEndpoints.eventSelfRegistration(eventId))
        .map { }

    override suspend fun unregister(eventId: String): ApiResult<Unit> =
        apiClient.deleteNoContent(ApiEndpoints.eventSelfRegistration(eventId))

    override suspend fun registerMember(eventId: String, memberId: String): ApiResult<String> =
        apiClient
            .post<RegistrationDto>(
                ApiEndpoints.eventRegistrations(eventId),
                RegistrationCreateDto(memberId),
            )
            .map { it.id }

    override suspend fun removeRegistration(
        eventId: String,
        registrationId: String,
    ): ApiResult<Unit> =
        apiClient.deleteNoContent(ApiEndpoints.eventRegistration(eventId, registrationId))

    override suspend fun memberOptions(search: String?): ApiResult<List<MemberOption>> {
        if (memberCursorComplete()) {
            return ApiResult.Success(
                members.search(search.orEmpty()).first()
                    .take(PICK_PAGE_SIZE)
                    .map { MemberOption(it.id, it.memberNumber, "${it.firstName} ${it.lastName}") },
            )
        }

        return apiClient
            .get<List<MemberOptionDto>>(ApiEndpoints.MEMBERS) {
                parameter("page", 1)
                parameter("per_page", PICK_PAGE_SIZE)
                if (!search.isNullOrBlank()) parameter("search", search)
            }
            .map { dtos ->
                dtos.map {
                    MemberOption(it.id, it.memberNumber, "${it.firstName} ${it.lastName}")
                }
            }
    }

    override suspend fun save(id: String?, draft: EventDraft): String {
        val recordId = id ?: UUID.randomUUID().toString()
        val creating = id == null
        val payload = if (creating) {
            draft.toCreatePayload(recordId)?.let { json.encodeToString(it) }
        } else {
            draft.toUpdatePayload()?.let { json.encodeToString(it) }
        }
        // Null only for a draft with no start, which the form's own validation
        // does not allow through. Returning the id regardless keeps the caller
        // simple; nothing was queued, so nothing will be sent.
        if (payload != null) {
            writes.enqueue(
                entity = EventSyncCollection.COLLECTION,
                recordId = recordId,
                op = if (creating) PendingWrite.OP_CREATE else PendingWrite.OP_UPDATE,
                payloadJson = payload,
                label = draft.title.trim(),
            )
        }
        return recordId
    }

    override fun pendingIds(): Flow<Set<String>> =
        writes.pending(EventSyncCollection.COLLECTION)
            .map { queued -> queued.mapTo(mutableSetOf()) { it.recordId } }

    /** See `DefaultMembersRepository.draftOf` for why this swallows a bad payload. */
    private fun draftOf(write: PendingWrite): EventDraft? = runCatching {
        if (write.op == PendingWrite.OP_CREATE) {
            json.decodeFromString<EventCreatePayload>(write.payloadJson).toDraft()
        } else {
            json.decodeFromString<EventUpdatePayload>(write.payloadJson).toDraft()
        }
    }.getOrNull()

    private suspend fun memberCursorComplete(): Boolean =
        cursors.bootstrapCompleteStream(MEMBERS_COLLECTION).first()

    private companion object {
        /** The server's `per_page` maximum (`le=100` on the list route). */
        const val OVERLAY_WINDOW = 100

        /** More than a sheet shows anyway; search narrows, paging never pays. */
        const val PICK_PAGE_SIZE = 100

        /**
         * Owned by feature:members, but features must not depend on each
         * other — the collection name is part of the sync protocol, not of a
         * module. Same trade-off as the attendance pick list.
         */
        const val MEMBERS_COLLECTION = "members"
    }
}

private fun Event.withDraft(draft: EventDraft) = copy(
    title = draft.title,
    description = draft.description,
    type = draft.eventType,
    location = draft.location,
    startsAt = draft.startsAt ?: startsAt,
    endsAt = draft.endsAt,
    allDay = draft.allDay,
    registrationRequired = draft.registrationRequired,
    maxParticipants = draft.maxParticipants,
)

/**
 * An event that exists only on this device so far.
 *
 * `registeredCount` is zero and `isRegistered` false because nobody can have
 * signed up for something the server has never heard of.
 */
private fun EventDraft.asNewEvent(id: String) = Event(
    id = id,
    title = title,
    description = description,
    type = eventType,
    location = location,
    startsAt = startsAt.orEmpty(),
    endsAt = endsAt,
    allDay = allDay,
    registrationRequired = registrationRequired,
    registrationDeadline = null,
    registeredCount = 0,
    maxParticipants = maxParticipants,
    status = "scheduled",
    isRegistered = false,
    competitionName = null,
)

internal fun EventCreatePayload.toDraft() = EventDraft(
    title = title,
    description = description,
    eventType = eventType,
    location = location,
    startsAt = startsAt,
    endsAt = endsAt,
    allDay = allDay,
    registrationRequired = registrationRequired,
    maxParticipants = maxParticipants,
)

internal fun EventUpdatePayload.toDraft() = EventDraft(
    title = title,
    description = description,
    eventType = eventType,
    location = location,
    startsAt = startsAt,
    endsAt = endsAt,
    allDay = allDay,
    registrationRequired = registrationRequired,
    maxParticipants = maxParticipants,
)

@Serializable
internal data class RegistrationDto(val id: String)

/** The body of the board-level register call — the member, nothing else. */
@Serializable
internal data class RegistrationCreateDto(@SerialName("member_id") val memberId: String)

/** The slice of the member list the add sheet needs. */
@Serializable
internal data class MemberOptionDto(
    val id: String,
    @SerialName("member_number") val memberNumber: String = "",
    @SerialName("first_name") val firstName: String = "",
    @SerialName("last_name") val lastName: String = "",
)

@Module
@InstallIn(SingletonComponent::class)
abstract class EventsModule {
    @Binds
    abstract fun bindEventsRepository(impl: DefaultEventsRepository): EventsRepository
}
