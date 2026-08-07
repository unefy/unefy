package com.unefy.core.auth

import com.unefy.core.network.ApiEndpoints
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.respond
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.defaultRequest
import io.ktor.http.ContentType
import io.ktor.http.HttpStatusCode
import io.ktor.http.contentType
import io.ktor.http.headersOf
import io.ktor.serialization.kotlinx.json.json
import io.ktor.utils.io.ByteReadChannel
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import org.junit.Test

/**
 * The Google calls against a stubbed backend.
 *
 * What can actually go wrong here is decoding and status mapping: a renamed
 * field decodes to its default and the app signs nobody in, and a 412 that is
 * read as a generic failure tells a member "sign-in failed" when the truth is
 * "you have no club yet".
 */
class GoogleTokenApiTest {

    private fun api(
        status: HttpStatusCode,
        body: String,
        onRequest: (String) -> Unit = {},
    ): TokenApi {
        val engine = MockEngine { request ->
            onRequest(request.url.encodedPath)
            respond(
                content = ByteReadChannel(body),
                status = status,
                headers = headersOf("Content-Type", ContentType.Application.Json.toString()),
            )
        }
        val client = HttpClient(engine) {
            expectSuccess = false
            install(ContentNegotiation) { json(Json { ignoreUnknownKeys = true }) }
            defaultRequest {
                url("http://backend.test")
                contentType(ContentType.Application.Json)
            }
        }
        return TokenApi(client, Clock { 1_000L })
    }

    @Test
    fun `nonce is read from the envelope`() = runTest {
        var path: String? = null
        val result = api(
            HttpStatusCode.OK,
            """{"data":{"nonce":"n-1","expires_in":600}}""",
        ) { path = it }.googleNonce()

        assertEquals(ApiEndpoints.AUTH_GOOGLE_NONCE, path)
        assertIs<ApiResult.Success<String>>(result)
        assertEquals("n-1", result.data)
    }

    @Test
    fun `server without google credentials answers 503`() = runTest {
        val result = api(
            HttpStatusCode.ServiceUnavailable,
            """{"error":{"code":"GOOGLE_NOT_CONFIGURED","message":"nope"}}""",
        ).googleNonce()

        val failure = assertIs<ApiResult.Failure>(result)
        val error = assertIs<ApiError.Http>(failure.error)
        assertEquals(503, error.status)
        assertEquals("GOOGLE_NOT_CONFIGURED", error.code)
    }

    @Test
    fun `sign-in yields tokens and a session`() = runTest {
        var path: String? = null
        val result = api(
            HttpStatusCode.OK,
            """
            {"data":{
              "access_token":"acc","refresh_token":"ref","access_expires_in":900,
              "user":{"id":"u1","name":"Andrea","email":"a@example.org","locale":"de"},
              "tenant":{"id":"t1","name":"SV Test","slug":"sv","short_name":"SVT"},
              "role":"member"
            }}
            """.trimIndent(),
        ) { path = it }.googleSignIn("id-token", "n-1")

        assertEquals(ApiEndpoints.AUTH_GOOGLE_SIGN_IN, path)
        val success = assertIs<ApiResult.Success<Pair<*, *>>>(result)
        val (tokens, session) = success.data
        assertEquals("acc", (tokens as com.unefy.core.model.AuthTokens).accessToken)
        // 1_000 from the fake clock plus the 900s the server granted.
        assertEquals(1_900L, tokens.accessExpiresAtEpochSeconds)
        assertEquals("t1", (session as com.unefy.core.model.Session).tenant.id)
        assertEquals("member", session.role)
    }

    @Test
    fun `id token sent as id_token`() = runTest {
        val engine = MockEngine { request ->
            val body = request.body.toString()
            assertTrue(body.contains("id_token"), "expected snake_case field, got: $body")
            respond(
                content = ByteReadChannel("""{"error":{"code":"FORBIDDEN","message":"no"}}"""),
                status = HttpStatusCode.Forbidden,
                headers = headersOf("Content-Type", ContentType.Application.Json.toString()),
            )
        }
        val client = HttpClient(engine) {
            expectSuccess = false
            install(ContentNegotiation) { json(Json { ignoreUnknownKeys = true }) }
            defaultRequest {
                url("http://backend.test")
                contentType(ContentType.Application.Json)
            }
        }
        val result = TokenApi(client, Clock { 0L }).googleSignIn("id-token", "n-1")
        assertIs<ApiResult.Failure>(result)
    }

    @Test
    fun `account without a club is distinguishable`() = runTest {
        val result = api(
            HttpStatusCode.PreconditionFailed,
            """{"error":{"code":"PRECONDITION_FAILED","message":"No active membership"}}""",
        ).googleSignIn("id-token", "n-1")

        val failure = assertIs<ApiResult.Failure>(result)
        val error = assertIs<ApiError.Http>(failure.error)
        assertEquals(412, error.status)
    }
}
