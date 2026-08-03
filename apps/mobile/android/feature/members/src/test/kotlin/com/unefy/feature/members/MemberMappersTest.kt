package com.unefy.feature.members

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The same member travels two roads: DTO → mirror row → domain, and DTO → domain
 * directly. Three hand-written mappers copy the same fifteen fields, and each
 * uses named arguments — so a field added to the model and forgotten in one of
 * them still compiles and silently drops the value on exactly one path. This
 * test is the compile error the mappers cannot give: every field is set to a
 * distinct non-default value, so a dropped one breaks the equality.
 */
class MemberMappersTest {

    @Test
    fun `the mirror path and the network path agree on every shared field`() {
        val dto = MemberDto(
            id = "id-1",
            memberNumber = "M-001",
            firstName = "Alice",
            lastName = "Example",
            email = "alice@example.org",
            phone = "030 1234",
            mobile = "0170 5678",
            birthday = "1990-04-01",
            street = "Musterweg 1",
            zipCode = "10115",
            city = "Berlin",
            status = "active",
            category = "adult",
            joinedAt = "2024-01-01",
            leftAt = "2026-12-31",
            iban = "DE02120300000000202051",
        )

        val viaMirror = dto.toRow(generation = 7L).toDomain()
        val direct = dto.toDomain()

        // The mirror deliberately never carries the IBAN — the one sanctioned
        // difference between the two roads.
        assertEquals(direct.copy(iban = null), viaMirror)
    }
}
