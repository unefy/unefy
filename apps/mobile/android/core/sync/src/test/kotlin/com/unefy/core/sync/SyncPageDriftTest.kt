package com.unefy.core.sync

import com.unefy.core.testing.MobileContract
import org.junit.Test

/** The sync envelope against the committed backend contract. */
class SyncPageDriftTest {

    @Test
    fun `SyncMeta mirrors the server's SyncMeta`() {
        MobileContract.assertMirrors(SyncMeta.serializer().descriptor, "SyncMeta")
    }

    @Test
    fun `SyncTombstone mirrors Tombstone`() {
        MobileContract.assertMirrors(SyncTombstone.serializer().descriptor, "Tombstone")
    }
}
