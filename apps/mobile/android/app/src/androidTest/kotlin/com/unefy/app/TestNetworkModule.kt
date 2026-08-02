package com.unefy.app

import com.unefy.core.network.ApiEndpoints
import com.unefy.core.network.NetworkModule
import dagger.Module
import dagger.Provides
import dagger.hilt.components.SingletonComponent
import dagger.hilt.testing.TestInstallIn
import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.respond
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.defaultRequest
import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.http.contentType
import io.ktor.http.headersOf
import io.ktor.serialization.kotlinx.json.json
import javax.inject.Singleton
import kotlinx.serialization.json.Json

/**
 * Swaps the Ktor engine, and nothing else.
 *
 * Faking the repositories instead would hide the layer most likely to break the
 * screens under test: envelope handling and DTO decoding. Here the real
 * `ApiClient` and the real repositories run against canned bodies, so a DTO that
 * no longer matches shows up as a screen in its error state rather than as a
 * green test.
 *
 * The Auth plugin is deliberately absent — this module answers every request, so
 * there is no 401 to refresh against, and leaving it out keeps the encrypted
 * token store out of a navigation test.
 */
@Module
@TestInstallIn(components = [SingletonComponent::class], replaces = [NetworkModule::class])
object TestNetworkModule {

    @Provides
    @Singleton
    fun provideJson(): Json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        isLenient = true
    }

    @Provides
    @Singleton
    fun provideHttpClient(json: Json): HttpClient = HttpClient(MockEngine) {
        expectSuccess = false

        install(ContentNegotiation) { json(json) }

        engine {
            addHandler { request ->
                respond(
                    content = bodyFor(request.url.encodedPath),
                    status = HttpStatusCode.OK,
                    headers = headersOf(HttpHeaders.ContentType, ContentType.Application.Json.toString()),
                )
            }
        }

        defaultRequest {
            url("http://localhost")
            contentType(ContentType.Application.Json)
        }
    }

    /**
     * Empty collections rather than fixtures: this test asks whether every screen
     * composes, and an empty list exercises the empty state, which is the branch
     * a freshly opened section shows most often anyway. Endpoints returning a
     * single object need a real body — a list would fail to decode and turn the
     * screen into an error state without saying why.
     */
    private fun bodyFor(path: String): String = when (path) {
        ApiEndpoints.MEMBERS_ME -> """{"data":$MEMBER}"""
        ApiEndpoints.DUES_SUMMARY -> """{"data":$DUES_SUMMARY}"""
        // A real seed, so the check-in screen actually encodes and draws a QR
        // during the smoke test rather than falling back to its error state.
        ApiEndpoints.ATTENDANCE_ME_SEED -> """{"data":$SEED}"""
        // Non-empty, so the manual pick list has something to show and the
        // members screen renders rows rather than its empty state.
        ApiEndpoints.MEMBERS -> """{"data":[$MEMBER]}"""
        // One open session, so the scanner preselects it and the manual action
        // appears — it is hidden without a session to check into.
        ApiEndpoints.ATTENDANCE_SESSIONS -> """{"data":[$SESSION]}"""
        else -> """{"data":[]}"""
    }

    private const val MEMBER = """
        {
          "id": "00000000-0000-0000-0000-000000000001",
          "member_number": "1",
          "first_name": "Test",
          "last_name": "Mitglied",
          "joined_at": "2026-01-01"
        }
    """

    private const val SESSION = """
        {
          "id": "00000000-0000-0000-0000-0000000000aa",
          "title": "Übungsabend",
          "opens_at": "2026-08-02T17:00:00+00:00",
          "closes_at": "2026-08-02T21:00:00+00:00",
          "status": "open",
          "record_count": 0
        }
    """

    private const val DUES_SUMMARY = """
        {"open_count": 0, "open_amount": "0", "paid_count": 0, "paid_amount": "0"}
    """

    // Expiry far in the future so the screen never decides the seed is stale
    // and shows the offline note instead of a plain code.
    private const val SEED = """
        {
          "member_ref": "AAAAAAAAAAAAAAAA",
          "seed": "DRNQW4ABVQPCVEXQQWBUVKVBSRZH6XCMZ2I7CNYGQHJU6H4FLYAA",
          "tenant_id": "11111111-1111-1111-1111-111111111111",
          "expires_at": 4102444800,
          "interval_seconds": 30,
          "algorithm": "uf1"
        }
    """
}
