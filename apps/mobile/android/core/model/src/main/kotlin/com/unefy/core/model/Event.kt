package com.unefy.core.model

/** A club event. Mirrors the backend's event response, minus the fields no screen shows. */
data class Event(
    val id: String,
    val title: String,
    val description: String?,
    val type: String?,
    val location: String?,
    /** ISO-8601 instant, e.g. `2026-02-20T19:00:00Z`. */
    val startsAt: String,
    val endsAt: String?,
    val allDay: Boolean,
    val registrationRequired: Boolean,
    /** ISO instant after which registration is refused, or null for no cut-off. */
    val registrationDeadline: String?,
    val registeredCount: Int,
    val maxParticipants: Int?,
    val status: String?,
    /** Whether the signed-in member is on this event. Comes from the backend. */
    val isRegistered: Boolean,
) {
    /** Null when the event has no cap — an unbounded event has no "full" state. */
    val capacityRatio: Float?
        get() = maxParticipants?.takeIf { it > 0 }?.let { registeredCount.toFloat() / it }

    val isFull: Boolean get() = capacityRatio?.let { it >= 1f } == true

    /**
     * Whether a member could still sign up, given the current instant.
     *
     * ISO-8601 UTC instants sort lexicographically, so a string comparison is
     * correct and avoids parsing a date on every row.
     */
    fun registrationOpen(nowIso: String): Boolean =
        registrationRequired &&
            !isFull &&
            (registrationDeadline == null || registrationDeadline > nowIso) &&
            startsAt > nowIso
}
