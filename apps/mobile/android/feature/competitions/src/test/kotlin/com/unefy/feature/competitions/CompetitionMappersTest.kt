package com.unefy.feature.competitions

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * DTO → mirror row → domain must agree with DTO → domain, including the
 * disciplines round-trip through the single joined column.
 */
class CompetitionMappersTest {

    @Test
    fun `the mirror path and the network path agree on every field`() {
        val dto = competition(disciplines = listOf("Luftgewehr 10m", "KK 50m"))

        assertEquals(dto.toDomain(), dto.toRow(generation = 7L).toDomain())
    }

    /** `"".split(sep)` yields `[""]`, not `[]` — the mapper must not fall for it. */
    @Test
    fun `no disciplines survive the round trip as an empty list`() {
        val dto = competition(disciplines = emptyList())

        assertEquals(emptyList<String>(), dto.toRow(generation = 7L).toDomain().disciplines)
    }

    @Test
    fun `a single discipline survives the round trip`() {
        val dto = competition(disciplines = listOf("Luftpistole 10m"))

        assertEquals(dto.toDomain(), dto.toRow(generation = 7L).toDomain())
    }

    private fun competition(disciplines: List<String>) = CompetitionDto(
        id = "c-1",
        name = "Königsschießen",
        description = "Traditionsschießen",
        competitionType = "internal",
        startDate = "2026-05-01",
        endDate = "2026-05-03",
        scoringUnit = "Ringe",
        scoringMode = "lowest_wins",
        disciplines = disciplines,
    )
}
