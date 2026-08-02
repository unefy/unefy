package com.unefy.core.auth

import com.unefy.core.network.ApiConfig
import com.unefy.core.network.TokenStore
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import io.ktor.client.HttpClient
import io.ktor.client.engine.okhttp.OkHttp
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.defaultRequest
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import javax.inject.Qualifier
import javax.inject.Singleton
import kotlinx.serialization.json.Json

/** The client without the Auth plugin — see [TokenApi] for why it must exist. */
@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class TokenHttpClient

/** Wall-clock time, injected so token expiry is testable. */
fun interface Clock {
    fun epochSeconds(): Long
}

@Module
@InstallIn(SingletonComponent::class)
object AuthModule {

    @Provides
    @Singleton
    fun provideClock(): Clock = Clock { System.currentTimeMillis() / MILLIS_PER_SECOND }

    @Provides
    @Singleton
    @TokenHttpClient
    fun provideTokenHttpClient(json: Json, config: ApiConfig): HttpClient = HttpClient(OkHttp) {
        expectSuccess = false
        install(ContentNegotiation) { json(json) }
        install(HttpTimeout) {
            requestTimeoutMillis = TOKEN_TIMEOUT_MS
            connectTimeoutMillis = TOKEN_TIMEOUT_MS
        }
        defaultRequest {
            url(config.baseUrl)
            contentType(ContentType.Application.Json)
        }
    }

    @Provides
    @Singleton
    fun provideTokenStore(tokenManager: TokenManager): TokenStore = tokenManager

    private const val MILLIS_PER_SECOND = 1000L
    private const val TOKEN_TIMEOUT_MS = 15_000L
}
