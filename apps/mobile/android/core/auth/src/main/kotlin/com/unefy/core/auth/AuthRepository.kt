package com.unefy.core.auth

import io.ktor.client.HttpClient
import io.ktor.client.plugins.auth.authProvider
import io.ktor.client.plugins.auth.providers.BearerAuthProvider
import com.unefy.core.model.Session
import com.unefy.core.network.ApiResult
import com.unefy.core.network.map
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow

/**
 * The app's entry point to authentication state.
 *
 * Only the dev-login endpoint is wired so far. Magic link, Google OAuth and
 * passkeys via Credential Manager are the MVP methods per apps/mobile/CLAUDE.md
 * and slot in here as further methods — the token handling below them does not
 * change.
 */
@Singleton
class AuthRepository @Inject constructor(
    private val tokenApi: TokenApi,
    private val tokenManager: TokenManager,
    private val httpClient: HttpClient,
    private val signOutTasks: Set<@JvmSuppressWildcards SignOutTask>,
) {
    val session: Flow<Session?> = tokenManager.session
    val isSignedIn: Flow<Boolean> = tokenManager.isSignedIn

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

    suspend fun signOut() {
        tokenManager.clear()
        forgetPreviousAccount()
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
