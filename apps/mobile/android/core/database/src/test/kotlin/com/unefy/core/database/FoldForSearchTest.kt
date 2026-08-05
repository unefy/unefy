package com.unefy.core.database

import java.util.Locale
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The half of the search that can be tested without SQLite.
 *
 * [foldForSearch] exists because SQLite folds ASCII only. The stored key and the
 * query both go through this function, so what matters is that both sides land on
 * the same string — which is a property of this function alone. The other half,
 * that `LIKE` then finds it, is in `SyncedMemberDaoTest` on a real database.
 */
class FoldForSearchTest {

    @Test
    fun `case is folded`() {
        assertEquals(foldForSearch("Müller"), foldForSearch("MÜLLER"))
    }

    @Test
    fun `umlauts fold to their base letter, as DIN 5007-1 sorts them`() {
        assertEquals("muller", foldForSearch("Müller"))
        assertEquals("ahnlich", foldForSearch("Ähnlich"))
        assertEquals("osterreich", foldForSearch("Österreich"))
    }

    /** So a search typed without umlauts still finds the member who has one. */
    @Test
    fun `a query typed without umlauts matches the folded key`() {
        assertEquals(foldForSearch("Müller"), foldForSearch("muller"))
    }

    @Test
    fun `eszett becomes ss`() {
        assertEquals("strasse", foldForSearch("Straße"))
    }

    /**
     * The reason [foldForSearch] passes a locale. On a Turkish device the
     * default-locale `lowercase()` turns "I" into a dotless "ı", and a member
     * named Iversen would stop being findable by anyone typing "iversen".
     */
    @Test
    fun `folding does not depend on the device locale`() {
        val default = Locale.getDefault()
        try {
            Locale.setDefault(Locale.forLanguageTag("tr"))
            assertEquals("iversen", foldForSearch("Iversen"))
        } finally {
            Locale.setDefault(default)
        }
    }

    /**
     * The keys are derived in the constructor rather than by the caller, so a row
     * cannot be stored with a key that does not match its name.
     */
    @Test
    fun `the entity derives its own keys`() {
        val member = SyncedMember(
            id = "1",
            memberNumber = "0042",
            firstName = "Jörg",
            lastName = "Grün",
            email = null,
            phone = null,
            mobile = null,
            birthday = null,
            gender = null,
            street = null,
            zipCode = null,
            city = null,
            status = "active",
            category = null,
            joinedAt = "2020-01-01",
            leftAt = null,
            generation = 1,
        )

        assertEquals("jorg grun 0042", member.searchKey)
        assertEquals("grun jorg", member.sortKey)
    }
}
