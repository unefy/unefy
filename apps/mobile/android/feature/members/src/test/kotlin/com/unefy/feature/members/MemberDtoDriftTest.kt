package com.unefy.feature.members

import com.unefy.core.testing.MobileContract
import org.junit.Test

/** The hand-written DTOs against the committed backend contract. */
class MemberDtoDriftTest {

    @Test
    fun `MemberDto mirrors MemberResponse`() {
        MobileContract.assertMirrors(MemberDto.serializer().descriptor, "MemberResponse")
    }

    @Test
    fun `DirectoryDto mirrors MemberDirectoryEntry`() {
        MobileContract.assertMirrors(DirectoryDto.serializer().descriptor, "MemberDirectoryEntry")
    }

    @Test
    fun `FederationMembershipDto mirrors FederationMembershipResponse`() {
        MobileContract.assertMirrors(
            FederationMembershipDto.serializer().descriptor,
            "FederationMembershipResponse",
        )
    }

    @Test
    fun `OfficeTermDto mirrors MemberFunctionResponse`() {
        MobileContract.assertMirrors(
            OfficeTermDto.serializer().descriptor,
            "MemberFunctionResponse",
        )
    }

    @Test
    fun `ConsentDtos mirror the consent schemas`() {
        MobileContract.assertMirrors(ConsentStateDto.serializer().descriptor, "ConsentState")
        MobileContract.assertMirrors(ConsentEntryDto.serializer().descriptor, "ConsentEntry")
        MobileContract.assertMirrors(ConsentOverviewDto.serializer().descriptor, "ConsentOverview")
    }
}
