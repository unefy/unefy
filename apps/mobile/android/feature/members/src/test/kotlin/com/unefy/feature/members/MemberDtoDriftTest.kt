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
}
