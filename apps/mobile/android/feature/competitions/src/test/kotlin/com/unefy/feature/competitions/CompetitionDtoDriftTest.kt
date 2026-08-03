package com.unefy.feature.competitions

import com.unefy.core.testing.MobileContract
import org.junit.Test

/** The hand-written DTOs against the committed backend contract. */
class CompetitionDtoDriftTest {

    @Test
    fun `CompetitionDto mirrors CompetitionResponse`() {
        MobileContract.assertMirrors(CompetitionDto.serializer().descriptor, "CompetitionResponse")
    }

    @Test
    fun `ScoreboardRowDto mirrors ScoreboardRow`() {
        MobileContract.assertMirrors(ScoreboardRowDto.serializer().descriptor, "ScoreboardRow")
    }
}
