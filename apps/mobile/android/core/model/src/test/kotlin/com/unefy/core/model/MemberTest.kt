package com.unefy.core.model

import org.junit.Assert.assertEquals
import org.junit.Test

class MemberTest {

    @Test
    fun `initials take the first letter of each name`() {
        assertEquals("AW", member(first = "Andreas", last = "Widmer").initials)
    }

    @Test
    fun `initials survive names the app did not anticipate`() {
        assertEquals("Ö", member(first = "Örn", last = "").initials)
        assertEquals("", member(first = "", last = "").initials)
    }

    @Test
    fun `known status values map to their enum`() {
        assertEquals(MemberStatus.ACTIVE, MemberStatus.fromApi("active"))
        assertEquals(MemberStatus.INACTIVE, MemberStatus.fromApi("inactive"))
        assertEquals(MemberStatus.RESIGNED, MemberStatus.fromApi("resigned"))
    }

    @Test
    fun `status matching ignores case`() {
        assertEquals(MemberStatus.ACTIVE, MemberStatus.fromApi("ACTIVE"))
    }

    /**
     * The backend column is a free-form String(20). A value the app has never
     * seen must degrade, not crash — this is the regression guard for that.
     */
    @Test
    fun `unknown and missing status degrade to UNKNOWN`() {
        assertEquals(MemberStatus.UNKNOWN, MemberStatus.fromApi("suspended"))
        assertEquals(MemberStatus.UNKNOWN, MemberStatus.fromApi(null))
        assertEquals(MemberStatus.UNKNOWN, MemberStatus.fromApi(""))
    }

    @Test
    fun `the IBAN is masked down to its last four digits`() {
        assertEquals("•••• 2051", member(iban = "DE02120300000000202051").maskedIban)
    }

    @Test
    fun `a short or missing IBAN is passed through rather than mangled`() {
        assertEquals("DE02", member(iban = "DE02").maskedIban)
        assertEquals(null, member(iban = null).maskedIban)
    }

    @Test
    fun `the postal line joins what is present and is null when nothing is`() {
        assertEquals("72074 Tübingen", member(zipCode = "72074", city = "Tübingen").postalLine)
        assertEquals("Tübingen", member(city = "Tübingen").postalLine)
        assertEquals(null, member().postalLine)
    }

    private fun member(
        first: String = "Susanne",
        last: String = "Bauer",
        street: String? = null,
        zipCode: String? = null,
        city: String? = null,
        iban: String? = null,
    ) = Member(
        id = "1",
        memberNumber = "TV-012",
        firstName = first,
        lastName = last,
        email = null,
        phone = null,
        mobile = null,
        birthday = null,
        gender = null,
        street = street,
        zipCode = zipCode,
        city = city,
        status = MemberStatus.ACTIVE,
        category = null,
        joinedAt = "2007-04-10",
        leftAt = null,
        iban = iban,
    )
}
