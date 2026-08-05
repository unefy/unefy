package com.unefy.core.push

import android.content.Context
import android.util.Log
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import com.unefy.core.auth.TokenManager
import com.unefy.core.network.ApiClient
import com.unefy.core.network.ApiEndpoints
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.tasks.await
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
internal data class PushRegisterBody(val token: String, val platform: String = "android")

@Serializable
internal data class PushRegisteredDto(val registered: Boolean = false)

/**
 * Keeps this device's row on the server in step with its FCM token.
 *
 * The token *is* the device identity — no separate id. Registration is an
 * upsert, so calling it on every sign-in and every `onNewToken` is the whole
 * protocol; there is no local bookkeeping to get wrong.
 *
 * Two quiet exits, both by design:
 *
 * - **No Firebase.** A build without `google-services.json` (a fork, a
 *   self-hoster) has no default [FirebaseApp]; everything here becomes a no-op
 *   rather than a crash, because push is an enhancement and its absence must
 *   cost nothing.
 * - **Server says 503 `PUSH_DISABLED`.** A self-hosted backend without a
 *   Firebase project answers with a name, and the answer cannot change within
 *   a session — so it is latched, the same way the sync coordinator latches
 *   `NotPermitted`.
 */
@Singleton
class PushRegistrar @Inject constructor(
    @ApplicationContext private val context: Context,
    private val apiClient: ApiClient,
    private val tokenManager: TokenManager,
) {

    @Volatile
    private var serverDisabled = false

    /**
     * Registers whenever someone signs in — or switches clubs, for as long as
     * it is collected. Keyed on the tenant rather than the signed-in flag: a
     * tenant switch keeps the account signed in but unregisters push as part
     * of its clean-out, and without this nothing would register it again.
     * Launched from the activity alongside the sync coordinator.
     */
    suspend fun run() {
        tokenManager.session
            .map { it?.tenant?.id }
            .distinctUntilChanged()
            .filterNotNull()
            .collect { register() }
    }

    /** One registration attempt. Safe to call at any time, from any state. */
    suspend fun register(token: String? = null) {
        if (serverDisabled || !firebaseAvailable()) return
        val fcmToken = token ?: currentToken() ?: return

        val result = apiClient.post<PushRegisteredDto>(
            ApiEndpoints.PUSH_DEVICES,
            body = PushRegisterBody(fcmToken),
        )
        when {
            result is ApiResult.Failure && result.error.isPushDisabled() -> {
                serverDisabled = true
                Log.i(TAG, "push disabled on this server; not asking again")
            }

            result is ApiResult.Failure ->
                // Best-effort: the next sign-in or token rotation tries again.
                Log.w(TAG, "push registration failed: ${result.error}")
        }
    }

    /**
     * Tells the server to forget this device, then drops the token locally.
     *
     * Runs during sign-out *before* the session is cleared — see
     * `AuthRepository.signOut` for the ordering. Deleting the token as well
     * makes the next sign-in start with a fresh identity instead of moving the
     * old row around.
     */
    suspend fun unregister() {
        if (!firebaseAvailable()) return
        val fcmToken = currentToken() ?: return

        if (!serverDisabled) {
            // Best-effort by design: offline sign-out must not block on this.
            // A row left behind wakes a signed-out app, which ignores it — and
            // the row moves the moment the device registers under a new account.
            apiClient.postNoContent(
                ApiEndpoints.PUSH_DEVICES_UNREGISTER,
                body = PushRegisterBody(fcmToken),
            )
        }
        runCatching { FirebaseMessaging.getInstance().deleteToken().await() }
    }

    private fun firebaseAvailable(): Boolean = FirebaseApp.getApps(context).isNotEmpty()

    private suspend fun currentToken(): String? =
        runCatching { FirebaseMessaging.getInstance().token.await() }
            .onFailure { Log.w(TAG, "no FCM token available", it) }
            .getOrNull()

    private fun ApiError.isPushDisabled(): Boolean =
        this is ApiError.Http && status == 503 && code == "PUSH_DISABLED"

    private companion object {
        const val TAG = "PushRegistrar"
    }
}
