package com.unefy.core.sync

import com.unefy.core.network.ApiEndpoints
import io.ktor.client.HttpClient
import io.ktor.client.plugins.HttpTimeoutConfig
import io.ktor.client.plugins.sse.sse
import io.ktor.client.plugins.timeout
import io.ktor.client.request.HttpRequestBuilder
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.channelFlow
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * One change hint from the server: something in this collection moved.
 *
 * Deliberately not the row. The stream is per club but its readers hold different
 * roles, and `MemberResponse` carries bank details — broadcasting rows would move
 * the authorisation decision into the fan-out layer, where it would eventually be
 * made wrongly. So a hint says what to re-read, and the re-read goes through the
 * endpoint that already checks the role.
 */
@Serializable
data class ChangeHint(
    /**
     * The collection name, matching the sync route segment: "members", plural.
     * It comes from `collection_for_model` in backend/app/sync/registry.py, which
     * returns `Collection.name`.
     */
    val entity: String,
    val id: String? = null,
    /**
     * "upsert" or "delete". Read for logging only — a hint carries no
     * authorisation, so nothing is ever deleted on its word. Deletions come from
     * the tombstones in a sync page.
     */
    val op: String? = null,
    @SerialName("at") val at: String? = null,
)

/**
 * The doorbell: something changed, not what.
 *
 * Correctness lives in the pull, speed in the push. A hint that gets lost costs
 * latency and nothing else — the worst case is that the app is as fresh as its
 * last sync — which is why this can be a best-effort stream instead of a durable
 * per-device queue with ordering and replay.
 *
 * An interface so the coordinator can be tested without a socket.
 */
fun interface ChangeStream {
    /** Hints, for as long as the flow is collected. */
    fun hints(): Flow<ChangeHint>
}

/**
 * Turns off both clocks that would end a response meant to stay open. A named
 * function rather than an inline block so a test can pin it — the mock engine
 * cannot speak SSE, but it does not need to: the bug lives in this builder.
 */
internal fun HttpRequestBuilder.streamTimeouts() {
    timeout {
        requestTimeoutMillis = HttpTimeoutConfig.INFINITE_TIMEOUT_MS
        socketTimeoutMillis = HttpTimeoutConfig.INFINITE_TIMEOUT_MS
    }
}

@Singleton
class SseChangeStream @Inject constructor(
    private val httpClient: HttpClient,
    private val json: Json,
) : ChangeStream {

    /**
     * Ktor's own SSE plugin reconnects on its own and resends `Last-Event-ID`,
     * which the backend answers exactly rather than approximately: the SSE `id`
     * *is* the Redis stream id, so a reconnection after a tunnel flickers picks up
     * in the gap instead of skipping it silently.
     */
    override fun hints(): Flow<ChangeHint> = channelFlow {
        httpClient.sse(
            urlString = ApiEndpoints.STREAM,
            request = {
                // Without these the stream dies on a stopwatch and rebuilds itself
                // forever. Two different clocks kill it:
                //
                // - `requestTimeoutMillis`: `HttpTimeout` in NetworkModule caps
                //   *every* request at 30 s, and for a response that is meant to
                //   stay open that is a lifetime limit.
                // - `socketTimeoutMillis`: never set anywhere, so the OkHttp
                //   engine's 10-second read timeout applies — and the server's
                //   heartbeat comes every 25 s. The socket died between
                //   heartbeats, every single time.
                //
                // The failure is nasty because it looks like success: the stream
                // reconnects on its own, so hints mostly still arrive — but every
                // rebuild has a blind gap, and a doorbell rung in that gap is
                // lost (no frame was ever received, so there is no `Last-Event-ID`
                // to resume from). Found on the device: the connection log showed
                // a fresh stream every 13 seconds, and renames landed in the gaps.
                streamTimeouts()
            },
        ) {
            incoming.collect { event ->
                val data = event.data ?: return@collect
                // A malformed frame is dropped rather than allowed to tear down the
                // stream: this is a latency optimisation, and a hint nobody can
                // parse is worth exactly one missed refresh.
                val hint = runCatching { json.decodeFromString<ChangeHint>(data) }.getOrNull()
                if (hint != null) send(hint)
            }
        }
    }
}
