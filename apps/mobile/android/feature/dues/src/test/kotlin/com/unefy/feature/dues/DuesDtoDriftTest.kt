package com.unefy.feature.dues

import com.unefy.core.testing.MobileContract
import org.junit.Test

/** The hand-written DTOs against the committed backend contract. */
class DuesDtoDriftTest {

    @Test
    fun `DuesDto mirrors DueResponse`() {
        MobileContract.assertMirrors(DuesDto.serializer().descriptor, "DueResponse")
    }

    @Test
    fun `DuesSummaryDto mirrors DueSummaryResponse`() {
        MobileContract.assertMirrors(
            DuesSummaryDto.serializer().descriptor,
            "DueSummaryResponse",
        )
    }
}
