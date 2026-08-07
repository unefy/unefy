package com.unefy.feature.events

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What the event form puts on the wire, and what it refuses to.
 *
 * The validation half matters most: the server rejects an event that ends
 * before it starts, and with a queue between the two that rejection arrives
 * hours after the typing — by which time nobody remembers what they typed. So
 * the form has to catch it while the person is still looking at it.
 */
class EventWriteTest {

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    private val start = "2026-09-01T17:00:00Z"

    // --- Validation ---

    @Test
    fun `an event needs a title and a start`() {
        assertTrue(EventDraft(title = "Vereinsabend", startsAt = start).isComplete)
        assertFalse(EventDraft(title = "  ", startsAt = start).isComplete)
        assertFalse(EventDraft(title = "Vereinsabend", startsAt = null).isComplete)
    }

    @Test
    fun `an end before the start is refused here, not by the server hours later`() {
        val draft = EventDraft(
            title = "Vereinsabend",
            startsAt = start,
            endsAt = "2026-09-01T16:00:00Z",
        )

        assertTrue(draft.endsBeforeItStarts)
        assertFalse(draft.isComplete)
    }

    @Test
    fun `an end after the start is fine, and so is no end at all`() {
        val ranged = EventDraft(
            title = "Vereinsabend",
            startsAt = start,
            endsAt = "2026-09-01T20:00:00Z",
        )
        val open = EventDraft(title = "Vereinsabend", startsAt = start, endsAt = null)

        assertFalse(ranged.endsBeforeItStarts)
        assertTrue(ranged.isComplete)
        assertFalse(open.endsBeforeItStarts)
        assertTrue(open.isComplete)
    }

    @Test
    fun `instants compare as strings because they are UTC and zero-padded`() {
        // Which is why `endsBeforeItStarts` can be a string comparison at all.
        // The field always writes `Instant.toString()`, so both sides are the
        // same shape and lexicographic order is chronological order. A local
        // offset in either would break that silently.
        assertTrue("2026-09-01T16:00:00Z" < "2026-09-01T17:00:00Z")
        assertTrue("2026-09-01T17:00:00Z" < "2026-12-01T09:00:00Z")
    }

    // --- Payloads ---

    @Test
    fun `the creation carries the id the device chose`() {
        val payload = EventDraft(title = "Vereinsabend", startsAt = start).toCreatePayload("ev-1")

        assertEquals("ev-1", payload?.id)
    }

    @Test
    fun `a draft with no start yields no payload, so nothing can be queued`() {
        assertNull(EventDraft(title = "Vereinsabend", startsAt = null).toCreatePayload("ev-1"))
        assertNull(EventDraft(title = "Vereinsabend", startsAt = null).toUpdatePayload())
    }

    @Test
    fun `blank optional fields travel as null`() {
        val payload = EventDraft(
            title = "  Vereinsabend ",
            startsAt = start,
            description = "   ",
            location = "",
        ).toCreatePayload("ev-1")

        assertEquals("Vereinsabend", payload?.title)
        assertNull(payload?.description)
        assertNull(payload?.location)
    }

    @Test
    fun `an update carries no id, because a PATCH addresses one in the path`() {
        val encoded = json.encodeToString(
            EventDraft(title = "Vereinsabend", startsAt = start).toUpdatePayload()!!,
        )

        assertTrue("id" !in json.parseToJsonElement(encoded).jsonObject)
    }

    @Test
    fun `the event type is one the server actually accepts`() {
        // EVENT_TYPE_PATTERN in backend/app/schemas/event.py is the authority:
        // training, meeting, celebration, competition, other. A value outside
        // it is a 422 the queue would only surface much later.
        val allowed = setOf("training", "meeting", "celebration", "competition", "other")
        val encoded = json.encodeToString(
            EventDraft(title = "T", startsAt = start, eventType = "celebration")
                .toCreatePayload("ev-1")!!,
        )

        val type = json.parseToJsonElement(encoded).jsonObject["event_type"]?.jsonPrimitive?.content
        assertTrue(type in allowed)
        // And the default the draft starts on, which is what an untouched form
        // sends.
        assertTrue(EventDraft().eventType in allowed)
    }

    @Test
    fun `a round trip through the payload keeps every field`() {
        // The form reopens on the queued payload, not on the mirror, so a field
        // lost in this conversion is a field the second edit silently clears.
        val draft = EventDraft(
            title = "Vereinsabend",
            description = "Mit Grillen",
            eventType = "celebration",
            location = "Schützenhaus",
            startsAt = start,
            endsAt = "2026-09-01T21:00:00Z",
            allDay = false,
            registrationRequired = true,
            maxParticipants = 40,
        )

        assertEquals(draft, draft.toCreatePayload("ev-1")!!.toDraft())
        assertEquals(draft, draft.toUpdatePayload()!!.toDraft())
    }
}
