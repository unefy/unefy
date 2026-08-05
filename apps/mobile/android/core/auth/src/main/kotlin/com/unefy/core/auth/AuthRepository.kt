package com.unefy.core.auth

import com.unefy.core.model.Session
import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiEndpoints
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import com.unefy.core.network.map
import io.ktor.client.HttpClient
import io.ktor.client.plugins.auth.authProvider
import io.ktor.client.plugins.auth.providers.BearerAuthProvider
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * The app's entry point to authentication state.
 *
 * Production sign-in is the mailed one-time code ([requestLoginCode] /
 * [verifyLoginCode]); [devLogin] stays as the DEBUG shortcut. Google OAuth and
 * passkeys via Credential Manager are the remaining MVP methods per
 * apps/mobile/CLAUDE.md and slot in here — the token handling does not change.
 */
@Singleton
class AuthRepository @Inject constructor(
    private val tokenApi: TokenApi,
    private val tokenManager: TokenManager,
    private val httpClient: HttpClient,
    private val apiClient: ApiClient,
    private val clock: Clock,
    private val signOutTasks: Set<@JvmSuppressWildcards SignOutTask>,
) {
    val session: Flow<Session?> = tokenManager.session
    val isSignedIn: Flow<Boolean> = tokenManager.isSignedIn

    /** Asks the backend to mail a one-time login code. */
    suspend fun requestLoginCode(email: String): ApiResult<Unit> =
        tokenApi.requestLoginCode(email.trim())

    /** Redeems the mailed code; on success the session flow flips to signed-in. */
    suspend fun verifyLoginCode(email: String, code: String): ApiResult<Session> {
        val result = tokenApi.verifyLoginCode(email.trim(), code.trim())
        if (result is ApiResult.Success) {
            val (tokens, session) = result.data
            // Same order as devLogin: the previous account's leftovers go
            // first, while its tokens are still valid.
            forgetPreviousAccount()
            tokenManager.persist(tokens, session)
        }
        return result.map { (_, session) -> session }
    }

    suspend fun devLogin(email: String): ApiResult<Session> {
        val result = tokenApi.devLogin(email.trim())
        if (result is ApiResult.Success) {
            val (tokens, session) = result.data
            // Before persisting: signing in without an intervening sign-out is
            // ordinary, and the cached token from last time must not outlive it.
            forgetPreviousAccount()
            tokenManager.persist(tokens, session)
        }
        return result.map { (_, session) -> session }
    }

    /** Every club this account belongs to, the current one marked. */
    suspend fun tenants(): ApiResult<List<TenantOption>> = apiClient
        .get<List<TenantOptionDto>>(ApiEndpoints.AUTH_TENANTS)
        .map { dtos ->
            dtos.map { TenantOption(it.tenantId, it.name, it.shortName, it.role, it.isCurrent) }
        }

    /**
     * Signs this device into another of the account's clubs.

     * A switch is a small sign-out with the account kept: the server re-issues
     * the token pair for the target club, and everything the old club left on
     * this device — mirrors, the check-in seed, the push registration, Ktor's
     * cached bearer — goes through the same [SignOutTask]s a sign-out runs.
     * Skipping them is how the last club's member list would end up on the
     * next club's screen.
     */
    suspend fun switchTenant(tenantId: String): ApiResult<Session> {
        val result = apiClient.post<TokenPairDto>(
            ApiEndpoints.AUTH_SWITCH_TENANT,
            body = SwitchTenantRequest(tenantId),
        )
        if (result is ApiResult.Failure) return ApiResult.Failure(result.error)

        val payload = (result as ApiResult.Success).data
        if (payload.user == null || payload.tenant == null) {
            return ApiResult.Failure(
                ApiError.Serialization(IllegalStateException("switch response missing user/tenant")),
            )
        }
        // Tasks first, with the old club's still-valid tokens — push
        // unregistration has to say goodbye as the old registration.
        forgetPreviousAccount()
        tokenManager.persist(payload.toTokens(clock), payload.toSession())
        return ApiResult.Success(payload.toSession())
    }

    suspend fun signOut() {
        // Tasks first, then the tokens: a task that has to tell the backend
        // something — push unregistration says "stop waking this phone" — needs
        // the session it is saying goodbye with. The reverse order handed those
        // tasks a 401. Mirrors [devLogin], where the tasks also run while the
        // old account's tokens are still there.
        forgetPreviousAccount()
        tokenManager.clear()
    }

    /**
     * Everything the last account left behind on this device.
     *
     * Two kinds of leftover, both of which produced wrong behaviour rather
     * than mere staleness:
     *
     * Ktor's bearer provider caches the token it first loaded and only revisits
     * it on a 401. After a sign-in as somebody else, requests kept going out as
     * the previous user — succeeding as them while the access token was still
     * valid, and failing on whatever the new account may not do.
     *
     * And feature-local stores. The check-in seed is the sharpest example: it
     * is that member's credential, and keeping it means the next person to sign
     * in on this phone hands out somebody else's code.
     */
    private suspend fun forgetPreviousAccount() {
        httpClient.authProvider<BearerAuthProvider>()?.clearToken()
        signOutTasks.forEach { it.onSignOut() }
    }
}

/**
 * Something a feature keeps per account and must drop when it changes.
 *
 * A multibinding rather than a list core:auth maintains: features are not
 * allowed to be named here, and a store nobody remembered to register is
 * exactly how the seed survived a sign-out.
 */
interface SignOutTask {
    suspend fun onSignOut()
}

/** One club the account could switch into. */
data class TenantOption(
    val id: String,
    val name: String,
    val shortName: String?,
    val role: String?,
    val isCurrent: Boolean,
)

@Serializable
internal data class TenantOptionDto(
    @SerialName("tenant_id") val tenantId: String,
    val name: String,
    @SerialName("short_name") val shortName: String? = null,
    val role: String? = null,
    @SerialName("is_current") val isCurrent: Boolean = false,
)

@Serializable
internal data class SwitchTenantRequest(@SerialName("tenant_id") val tenantId: String)
