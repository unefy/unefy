package com.unefy.feature.attendance

import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiResult
import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.respond
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.request.HttpRequestData
import io.ktor.http.ContentType
import io.ktor.http.HttpStatusCode
import io.ktor.http.headersOf
import io.ktor.serialization.kotlinx.json.json
import io.ktor.utils.io.ByteReadChannel
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The wire contract for the shooting details the range table enters.
 *
 * Tested here rather than through the view model, which cannot be built on the
 * JVM — it binds CameraX use cases in its constructor. What matters anyway lives
 * at this layer: the keys the server sends, the keys it expects back, and the one
 * property a form like this stands or falls on, that a wrong entry can be cleared
 * again.
 */
class ShootingDetailsTest {

    private val requests = mutableListOf<HttpRequestData>()

    private fun repository(body: String): DefaultShootingDetailRepository {
        val engine = MockEngine { request ->
            requests += request
            respond(
                content = ByteReadChannel("""{"data": $body}"""),
                status = HttpStatusCode.OK,
                headers = headersOf("Content-Type", ContentType.Application.Json.toString()),
            )
        }
        val client = HttpClient(engine) {
            install(ContentNegotiation) { json(Json { ignoreUnknownKeys = true }) }
        }
        return DefaultShootingDetailRepository(ApiClient(client))
    }

    private suspend fun HttpRequestData.bodyText(): String =
        (body as io.ktor.http.content.TextContent).text

    @Test
    fun `a session's details arrive keyed by attendance record`() = runTest {
        // Keyed, because the list that shows them is a list of check-ins: a row
        // has to find its own detail without scanning the whole answer.
        val repository = repository(
            """
            [
              {"id": "d1", "attendance_record_id": "r1", "club_discipline_id": "c1",
               "weapon_category": "luftdruck", "rounds_fired": 40},
              {"id": "d2", "attendance_record_id": "r2", "club_discipline_id": null,
               "weapon_category": null, "rounds_fired": null}
            ]
            """.trimIndent(),
        )

        val result = repository.forSession("session-1")

        val details = (result as ApiResult.Success).data
        assertEquals(setOf("r1", "r2"), details.keys)
        assertEquals("luftdruck", details["r1"]?.weaponCategory)
        assertEquals(40, details["r1"]?.roundsFired)
        // An empty detail row is not the same as no row: somebody opened the
        // sheet and saved nothing, and the form must show exactly that.
        assertNull(details["r2"]?.weaponCategory)
        assertTrue(requests.single().url.parameters["session_id"] == "session-1")
    }

    @Test
    fun `clearing a field sends null rather than leaving it out`() = runTest {
        // The property the form depends on. An omitted key means "leave as is" to
        // a PATCH, so a wrong discipline could never be taken back — the entry
        // would be permanent, which for a range book is worse than blank.
        val repository = repository(
            """{"id": "d1", "attendance_record_id": "r1", "club_discipline_id": null,
                "weapon_category": null, "rounds_fired": null}""",
        )

        repository.save("r1", clubDisciplineId = null, weaponCategory = null, roundsFired = null)

        val sent = requests.single().bodyText()
        assertTrue(sent, sent.contains("\"club_discipline_id\":null"))
        assertTrue(sent, sent.contains("\"weapon_category\":null"))
        assertTrue(sent, sent.contains("\"rounds_fired\":null"))
    }

    @Test
    fun `a save posts to the record it belongs to`() = runTest {
        val repository = repository(
            """{"id": "d1", "attendance_record_id": "r7", "club_discipline_id": "c1",
                "weapon_category": "kurzwaffe", "rounds_fired": 60}""",
        )

        val result = repository.save("r7", "c1", "kurzwaffe", 60)

        assertTrue(requests.single().url.encodedPath.endsWith("/records/r7"))
        // Taken from the answer, not from what was typed: the server is what the
        // range book will print.
        assertEquals("r7", (result as ApiResult.Success).data.attendanceRecordId)
    }

    @Test
    fun `disciplines keep their short name for the summary line`() = runTest {
        // "LG 10m" is what the range book prints and what fits on a phone row.
        val repository = repository(
            """[{"id": "c1", "name": "Luftgewehr", "short_name": "LG 10m", "is_active": true}]""",
        )

        val result = repository.disciplines()

        assertEquals("LG 10m", (result as ApiResult.Success).data.single().shortName)
    }
}
