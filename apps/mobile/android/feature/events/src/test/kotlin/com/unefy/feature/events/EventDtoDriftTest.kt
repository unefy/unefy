package com.unefy.feature.events

import com.unefy.core.testing.MobileContract
import org.junit.Test

/** The hand-written DTOs against the committed backend contract. */
class EventDtoDriftTest {

    @Test
    fun `EventDto mirrors EventResponse`() {
        MobileContract.assertMirrors(
            EventDto.serializer().descriptor,
            "EventResponse",
            // List-endpoint enrichment, merged as plain dict keys: the merge
            // always writes a bool and an int, never an explicit null, and the
            // sync payload omits them entirely - absence is what the defaults
            // are for.
            tolerateNonNullable = setOf("is_registered", "registered_count"),
        )
    }

    @Test
    fun `EventDetailDto mirrors EventResponse`() {
        MobileContract.assertMirrors(
            EventDetailDto.serializer().descriptor,
            "EventResponse",
            // Same merge as the list. `registrations` needs no tolerance: the
            // contract already exports it non-nullable because the detail
            // route always writes a list.
            tolerateNonNullable = setOf("is_registered", "registered_count"),
        )
    }

    @Test
    fun `EventRegistrationDto mirrors EventRegistrationResponse`() {
        MobileContract.assertMirrors(
            EventRegistrationDto.serializer().descriptor,
            "EventRegistrationResponse",
        )
    }

    @Test
    fun `RegistrationDto mirrors EventRegistrationResponse`() {
        MobileContract.assertMirrors(
            RegistrationDto.serializer().descriptor,
            "EventRegistrationResponse",
        )
    }
}
