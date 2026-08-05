package com.unefy.core.auth

import com.unefy.core.model.AuthTokens
import com.unefy.core.model.AuthUser
import com.unefy.core.model.Session
import com.unefy.core.model.Tenant
import com.unefy.core.network.ApiEndpoints
import com.unefy.core.network.ApiEnvelope
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.client.statement.HttpResponse
import io.ktor.http.isSuccess
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Auth calls that must not go through the authenticated client.
 *
 * Using [com.unefy.core.network.ApiClient] here would be circular — that client
 * asks [TokenManager] for tokens, and [TokenManager] needs this class to
 * refresh them. This one has no Auth plugin installed, which breaks the cycle
 * and also prevents a refresh attempt from recursing on its own 401.
 */
@Singleton
class TokenApi @Inject constructor(
    @TokenHttpClient private val client: HttpClient,
    private val clock: Clock,
) {
    sealed interface Result {
        data class Success(val tokens: AuthTokens) : Result

        /** The refresh token itself was rejected — the session is over. */
        data object Rejected : Result

        /** Transient: network down or backend error. Must not sign the user out. */
        data object Unavailable : Result
    }

    suspend fun refresh(refreshToken: String, tenantId: String? = null): Result = try {
        val response = client.post(ApiEndpoints.AUTH_REFRESH) {
            // The tenant travels along so a rotation cannot silently undo a
            // tenant switch — the server re-pins to the first club otherwise.
            setBody(RefreshRequest(refreshToken, tenantId))
        }
        val envelope: ApiEnvelope<TokenPairDto> = response.body()
        // Local val: `data` comes from another module, so it cannot smart-cast.
        val payload = envelope.data
        when {
            response.status.isSuccess() && payload != null ->
                Result.Success(payload.toTokens(clock))

            response.status.value in UNAUTHORIZED_RANGE -> Result.Rejected
            else -> Result.Unavailable
        }
    } catch (
        @Suppress("TooGenericExceptionCaught") e: Exception,
    ) {
        Result.Unavailable
    }

    suspend fun devLogin(email: String): ApiResult<Pair<AuthTokens, Session>> = try {
        val response = client.post(ApiEndpoints.AUTH_DEV_LOGIN) {
            setBody(DevLoginRequest(email))
        }
        response.toSessionResult()
    } catch (e: IOException) {
        ApiResult.Failure(ApiError.Network(e))
    } catch (
        @Suppress("TooGenericExceptionCaught") e: Exception,
    ) {
        ApiResult.Failure(ApiError.Unknown(e))
    }

    private suspend fun HttpResponse.toSessionResult(): ApiResult<Pair<AuthTokens, Session>> {
        val envelope: ApiEnvelope<TokenPairDto> = body()
        val payload = envelope.data
        return when {
            status.isSuccess() && payload?.user != null && payload.tenant != null ->
                ApiResult.Success(payload.toTokens(clock) to payload.toSession())

            status.isSuccess() -> ApiResult.Failure(
                ApiError.Serialization(IllegalStateException("login response missing user/tenant")),
            )

            status.value == 401 -> ApiResult.Failure(ApiError.Unauthorized)
            status.value == 403 -> ApiResult.Failure(ApiError.Forbidden)
            else -> ApiResult.Failure(
                ApiError.Http(status.value, envelope.error?.code, envelope.error?.message),
            )
        }
    }

    private companion object {
        val UNAUTHORIZED_RANGE = 400..403
    }
}

@Serializable
private data class RefreshRequest(
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("tenant_id") val tenantId: String? = null,
)

@Serializable
private data class DevLoginRequest(val email: String)

@Serializable
internal data class TokenPairDto(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("access_expires_in") val accessExpiresIn: Long = 0,
    val user: UserDto? = null,
    val tenant: TenantDto? = null,
    val role: String? = null,
)

@Serializable
internal data class UserDto(
    val id: String,
    val name: String? = null,
    val email: String,
    val locale: String? = null,
)

@Serializable
internal data class TenantDto(
    val id: String,
    val name: String,
    val slug: String? = null,
    @SerialName("short_name") val shortName: String? = null,
)

internal fun TokenPairDto.toTokens(clock: Clock) = AuthTokens(
    accessToken = accessToken,
    refreshToken = refreshToken,
    accessExpiresAtEpochSeconds = clock.epochSeconds() + accessExpiresIn,
)

internal fun TokenPairDto.toSession() = Session(
    user = AuthUser(
        id = requireNotNull(user).id,
        name = user.name,
        email = user.email,
        locale = user.locale,
    ),
    tenant = Tenant(
        id = requireNotNull(tenant).id,
        name = tenant.name,
        slug = tenant.slug,
        shortName = tenant.shortName,
    ),
    role = role.orEmpty(),
)
