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
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import javax.inject.Singleton
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

    private const val REQUEST_TIMEOUT_MS = 30_000L
    private const val CONNECT_TIMEOUT_MS = 10_000L
}
