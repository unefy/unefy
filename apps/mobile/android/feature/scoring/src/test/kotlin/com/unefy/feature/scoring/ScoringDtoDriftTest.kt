package com.unefy.feature.scoring

import com.unefy.core.testing.MobileContract
import org.junit.Test

/**
 * The hand-written DTOs against the committed backend contract.
 *
 * `EntryDetails` and `ShotDetail` matter more here than elsewhere: on the wire
 * they live inside `EntryResponse.details`, which is an untyped JSONB dict. The
 * server can therefore change that shape without any schema saying so, and this
 * is the only thing that would notice.
 */
class ScoringDtoDriftTest {

    @Test
    fun `EntryDto mirrors EntryResponse`() {
        MobileContract.assertMirrors(EntryDto.serializer().descriptor, "EntryResponse")
    }

    @Test
    fun `EntryDetailsDto mirrors EntryDetails`() {
        MobileContract.assertMirrors(EntryDetailsDto.serializer().descriptor, "EntryDetails")
    }

    @Test
    fun `ShotDetailDto mirrors ShotDetail`() {
        MobileContract.assertMirrors(ShotDetailDto.serializer().descriptor, "ShotDetail")
    }

    @Test
    fun `TargetTypeDto mirrors TargetTypeResponse`() {
        MobileContract.assertMirrors(
            TargetTypeDto.serializer().descriptor,
            "TargetTypeResponse",
        )
    }
}
