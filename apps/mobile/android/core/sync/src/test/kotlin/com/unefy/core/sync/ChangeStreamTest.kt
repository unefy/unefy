package com.unefy.core.sync

import io.ktor.client.plugins.HttpTimeoutCapability
import io.ktor.client.plugins.HttpTimeoutConfig
import io.ktor.client.request.HttpRequestBuilder
import org.junit.Assert.assertEquals
import org.junit.Test

class ChangeStreamTest {

    /**
     * The regression test for the flapping doorbell. Two clocks can kill a
     * response that is meant to stay open: the client-wide `requestTimeoutMillis`
     * (30 s) and the OkHttp engine's read timeout (10 s) — the server's
     * heartbeat comes every 25 s, so the second clock killed the stream between
     * heartbeats, every time. Each rebuild has a blind gap, and a hint rung in
     * the gap is lost for good: no frame was ever received, so there is no
     * `Last-Event-ID` to resume from. Found on the device, not by review: the
     * connection log showed a fresh `/api/v1/stream` every 13 seconds, and
     * renames landed in the gaps.
     */
    @Test
    fun `the stream request disables both lifetime clocks`() {
        val builder = HttpRequestBuilder()

        builder.streamTimeouts()

        val config = builder.getCapabilityOrNull(HttpTimeoutCapability)
        assertEquals(HttpTimeoutConfig.INFINITE_TIMEOUT_MS, config?.requestTimeoutMillis)
        assertEquals(HttpTimeoutConfig.INFINITE_TIMEOUT_MS, config?.socketTimeoutMillis)
    }
}
