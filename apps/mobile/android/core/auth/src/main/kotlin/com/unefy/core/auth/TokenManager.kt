package com.unefy.core.auth

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.unefy.core.model.AuthTokens
import com.unefy.core.model.AuthUser
import com.unefy.core.model.Session
import com.unefy.core.model.Tenant
import com.unefy.core.network.TokenStore
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

private val Context.authDataStore: DataStore<Preferences> by preferencesDataStore(name = "unefy_auth")

/**
 * Owns the session: encrypted tokens, the signed-in user and the active tenant.
 *
 * Implements [TokenStore] so the Ktor Auth plugin can read and refresh tokens
 * without knowing anything about Keystore or DataStore.
 */
@Singleton
class TokenManager @Inject constructor(
    @ApplicationContext private val context: Context,
    private val crypto: TokenCrypto,
    private val tokenApi: TokenApi,
) : TokenStore {

    /**
     * Serialises refreshes. Several requests can fail with 401 at once; without
     * this they would each burn a refresh token and race each other.
     */
    private val refreshMutex = Mutex()

    val session: Flow<Session?> = context.authDataStore.data.map { it.toSession() }

    val isSignedIn: Flow<Boolean> = context.authDataStore.data.map { it[Keys.ACCESS] != null }

    override suspend fun current(): AuthTokens? = context.authDataStore.data.first().toTokens()

    override suspend fun refresh(): AuthTokens? = refreshMutex.withLock {
        val refreshToken = current()?.refreshToken ?: return@withLock null
        val tenantId = context.authDataStore.data.first()[Keys.TENANT_ID]

        when (val result = tokenApi.refresh(refreshToken, tenantId)) {
            is TokenApi.Result.Success -> {
                persistTokens(result.tokens)
                result.tokens
            }
            // A dead refresh token is terminal: clear everything so the app
            // falls back to the login screen instead of retrying forever.
            TokenApi.Result.Rejected -> {
                clear()
                null
            }
            // A transient network failure must not sign the user out.
            TokenApi.Result.Unavailable -> null
        }
    }

    suspend fun persist(tokens: AuthTokens, session: Session) {
        context.authDataStore.edit { prefs ->
            prefs[Keys.ACCESS] = crypto.encrypt(tokens.accessToken)
            prefs[Keys.REFRESH] = crypto.encrypt(tokens.refreshToken)
            prefs[Keys.EXPIRES_AT] = tokens.accessExpiresAtEpochSeconds
            prefs[Keys.USER_ID] = session.user.id
            prefs[Keys.USER_EMAIL] = session.user.email
            session.user.name?.let { prefs[Keys.USER_NAME] = it }
            session.user.locale?.let { prefs[Keys.USER_LOCALE] = it }
            prefs[Keys.TENANT_ID] = session.tenant.id
            prefs[Keys.TENANT_NAME] = session.tenant.name
            session.tenant.slug?.let { prefs[Keys.TENANT_SLUG] = it }
            session.tenant.shortName?.let { prefs[Keys.TENANT_SHORT] = it }
            prefs[Keys.ROLE] = session.role
        }
    }

    suspend fun clear() {
        context.authDataStore.edit { it.clear() }
    }

    private suspend fun persistTokens(tokens: AuthTokens) {
        context.authDataStore.edit { prefs ->
            prefs[Keys.ACCESS] = crypto.encrypt(tokens.accessToken)
            prefs[Keys.REFRESH] = crypto.encrypt(tokens.refreshToken)
            prefs[Keys.EXPIRES_AT] = tokens.accessExpiresAtEpochSeconds
        }
    }

    private fun Preferences.toTokens(): AuthTokens? {
        val access = this[Keys.ACCESS]?.let(crypto::decrypt) ?: return null
        val refresh = this[Keys.REFRESH]?.let(crypto::decrypt) ?: return null
        return AuthTokens(access, refresh, this[Keys.EXPIRES_AT] ?: 0L)
    }

    private fun Preferences.toSession(): Session? {
        val userId = this[Keys.USER_ID] ?: return null
        val email = this[Keys.USER_EMAIL] ?: return null
        val tenantId = this[Keys.TENANT_ID] ?: return null
        val tenantName = this[Keys.TENANT_NAME] ?: return null
        return Session(
            user = AuthUser(userId, this[Keys.USER_NAME], email, this[Keys.USER_LOCALE]),
            tenant = Tenant(tenantId, tenantName, this[Keys.TENANT_SLUG], this[Keys.TENANT_SHORT]),
            role = this[Keys.ROLE].orEmpty(),
        )
    }

    private object Keys {
        val ACCESS = stringPreferencesKey("access_token_enc")
        val REFRESH = stringPreferencesKey("refresh_token_enc")
        val EXPIRES_AT = longPreferencesKey("access_expires_at")
        val USER_ID = stringPreferencesKey("user_id")
        val USER_EMAIL = stringPreferencesKey("user_email")
        val USER_NAME = stringPreferencesKey("user_name")
        val USER_LOCALE = stringPreferencesKey("user_locale")
        val TENANT_ID = stringPreferencesKey("tenant_id")
        val TENANT_NAME = stringPreferencesKey("tenant_name")
        val TENANT_SLUG = stringPreferencesKey("tenant_slug")
        val TENANT_SHORT = stringPreferencesKey("tenant_short_name")
        val ROLE = stringPreferencesKey("role")
    }
}
