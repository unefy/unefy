package com.unefy.core.auth

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
) {
    val session: Flow<Session?> = tokenManager.session
    val isSignedIn: Flow<Boolean> = tokenManager.isSignedIn

    suspend fun devLogin(email: String): ApiResult<Session> {
        val result = tokenApi.devLogin(email.trim())
        if (result is ApiResult.Success) {
            val (tokens, session) = result.data
            tokenManager.persist(tokens, session)
        }
        return result.map { (_, session) -> session }
    }

    suspend fun signOut() {
        tokenManager.clear()
    }
}
