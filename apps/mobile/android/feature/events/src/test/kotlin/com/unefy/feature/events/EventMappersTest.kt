package com.unefy.feature.events

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The same event travels two roads: DTO → mirror row → domain, and DTO → domain
 * directly (the overlay path). Both mappers use named arguments, so a field
 * added to the model and forgotten in one of them still compiles and silently
 * drops the value on one path. Every field carries a distinct non-default
 * value, so a dropped one breaks the equality.
 */
class EventMappersTest {

    @Test
    fun `the mirror path and the overlay path agree on every shared field`() {
        val dto = EventDto(
            id = "e-1",
            title = "Vereinsmeisterschaft",
            description = "Mit Siegerehrung",
            eventType = "competition",
            location = "Schießstand 1",
            startsAt = "2026-09-01T10:00:00Z",
            endsAt = "2026-09-01T16:00:00Z",
            allDay = false,
            registrationRequired = true,
            registrationDeadline = "2026-08-25T23:59:59Z",
            registeredCount = 17,
            maxParticipants = 40,
            status = "published",
            isRegistered = true,
            competitionName = "Königsschießen",
        )

        val viaMirror = dto.toRow(generation = 7L).toDomain()
        val direct = dto.toDomain()

        // The three overlay fields are the mirror's one sanctioned difference.
        assertEquals(
            direct.copy(isRegistered = false, registeredCount = 0, competitionName = null),
            viaMirror,
        )
    }
}
