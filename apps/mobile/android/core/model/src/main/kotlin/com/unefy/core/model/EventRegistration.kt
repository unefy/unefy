package com.unefy.core.model

/**
 * One name on an event's list. Comes only from the single-event endpoint —
 * never mirrored: the list is caller-visible state that changes with every
 * sign-up, and showing it stale would misname who is coming.
 */
data class EventRegistration(
    val id: String,
    val memberId: String,
    /** Joined first and last name; null when the backend could not resolve it. */
    val memberName: String?,
    /** `registered` or `waitlisted` — the backend's vocabulary, not ours. */
    val status: String,
    val note: String?,
) {
    val isWaitlisted: Boolean get() = status == "waitlisted"
}

/** The single event with everything the detail screen shows. */
data class EventDetail(
    val event: Event,
    val registrations: List<EventRegistration>,
)
