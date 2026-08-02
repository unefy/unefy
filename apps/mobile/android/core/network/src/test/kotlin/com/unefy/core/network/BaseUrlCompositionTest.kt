package com.unefy.core.network

import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.respond
import io.ktor.client.plugins.defaultRequest
import io.ktor.client.request.get
import io.ktor.http.HttpStatusCode
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Regression guard for the base-URL wiring.
 *
 * A client that silently drops the port or host produces a plain connection
 * failure on the device, which is indistinguishable from "no network" in the
 * UI. This test pins the composed URL so that class of bug fails in CI instead.
 */
class BaseUrlCompositionTest {

    private var requestedUrl: String? = null

    private fun client(baseUrl: String) = HttpClient(
        MockEngine { request ->
            requestedUrl = request.url.toString()
            respond(
                content = """{"data":null}""",
                status = HttpStatusCode.OK,
                headers = io.ktor.http.headersOf("Content-Type", "application/json"),
            )
        },
    ) {
        defaultRequest { url(baseUrl) }
    }

    @Test
    fun `absolute path keeps host and non-default port`() = runTest {
        client("http://10.0.0.109:8013").get("/api/v1/members")
        assertEquals("http://10.0.0.109:8013/api/v1/members", requestedUrl)
    }

    @Test
    fun `base url with a trailing slash behaves the same`() = runTest {
        client("http://10.0.0.109:8013/").get("/api/v1/members")
        assertEquals("http://10.0.0.109:8013/api/v1/members", requestedUrl)
    }

    @Test
    fun `emulator host alias is preserved`() = runTest {
        client("http://10.0.2.2:8013").get(ApiEndpoints.AUTH_DEV_LOGIN)
        assertEquals("http://10.0.2.2:8013/api/v1/auth/mobile/dev/login", requestedUrl)
    }
}
