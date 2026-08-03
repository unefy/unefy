package com.unefy.core.network

import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import io.ktor.client.HttpClient
import io.ktor.client.engine.okhttp.OkHttp
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.plugins.auth.Auth
import io.ktor.client.plugins.auth.providers.BearerTokens
import io.ktor.client.plugins.auth.providers.bearer
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.defaultRequest
import io.ktor.client.plugins.sse.SSE
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import javax.inject.Singleton
import kotlin.time.Duration.Companion.seconds
import kotlinx.serialization.json.Json

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideJson(): Json = Json {
        ignoreUnknownKeys = true // backend fields the app does not model yet
        explicitNulls = false
        isLenient = true
    }

    @Provides
    @Singleton
    fun provideHttpClient(
        json: Json,
        config: ApiConfig,
        tokenStore: TokenStore,
    ): HttpClient = HttpClient(OkHttp) {
        // Errors are decided from the envelope in ApiClient, not thrown by Ktor.
        expectSuccess = false

        install(ContentNegotiation) { json(json) }

        // The change stream. Ships inside ktor-client-core, and running through
        // the normal pipeline is the point: the Auth plugin below attaches the
        // bearer token and refreshes it on 401, so the stream needs no auth code
        // of its own and no token in the URL — which would otherwise end up in
        // RequestLoggingMiddleware and every proxy log on the way.
        install(SSE) {
            // The server sends a heartbeat every 25s (HEARTBEAT_SECONDS in
            // backend/app/events/stream.py), so a longer wait than that means the
            // connection is genuinely gone rather than quiet.
            maxReconnectionAttempts = Int.MAX_VALUE
            reconnectionTime = RECONNECT_DELAY
        }

        install(HttpTimeout) {
            requestTimeoutMillis = REQUEST_TIMEOUT_MS
            connectTimeoutMillis = CONNECT_TIMEOUT_MS
        }

        install(Auth) {
            bearer {
                loadTokens {
                    tokenStore.current()?.let { BearerTokens(it.accessToken, it.refreshToken) }
                }
                // Ktor calls this once on 401 and retries the request with the
                // result — the whole 401-refresh-retry flow the CLAUDE.md API
                // client pattern describes, without a hand-written interceptor.
                refreshTokens {
                    tokenStore.refresh()?.let { BearerTokens(it.accessToken, it.refreshToken) }
                }
                sendWithoutRequest { request ->
                    // Auth endpoints must not carry a stale bearer token.
                    val path = request.url.pathSegments
                        .filter { it.isNotEmpty() }
                        .joinToString(separator = "/", prefix = "/")
                    !path.startsWith(ApiEndpoints.AUTH_PREFIX)
                }
            }
        }

        defaultRequest {
            url(config.baseUrl)
            contentType(ContentType.Application.Json)
        }
    }

    /**
     * Applies to ordinary requests. The change stream overrides it per request
     * with an infinite value — a response designed to stay open for minutes cannot
     * live under a 30-second stopwatch. See `ChangeStream.hints`.
     */
    private const val REQUEST_TIMEOUT_MS = 30_000L
    private const val CONNECT_TIMEOUT_MS = 10_000L
    private val RECONNECT_DELAY = 3.seconds
}
