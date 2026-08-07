package com.unefy.core.auth

import android.content.Context
import androidx.credentials.CredentialManager
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import androidx.credentials.exceptions.GetCredentialCancellationException
import androidx.credentials.exceptions.GetCredentialException
import androidx.credentials.exceptions.NoCredentialException
import com.google.android.libraries.identity.googleid.GetGoogleIdOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import com.google.android.libraries.identity.googleid.GoogleIdTokenParsingException
import com.unefy.core.model.Session
import com.unefy.core.network.ApiError
import javax.inject.Inject
import javax.inject.Singleton

/**
 * The OAuth client id the ID token is minted for.
 *
 * The *web* client id, not the Android one — that is what Google's own
 * documentation calls `serverClientId`, and it is the value that ends up in
 * the token's `aud` claim for the backend to check. The Android client id is
 * never named anywhere in the app; it exists in the Google Cloud project so
 * that Google can tie the request to this package name and signing
 * certificate, and that binding is what stops another app asking for tokens
 * in our name.
 *
 * Blank in builds that ship without one — a fork, a CI build, a self-hoster
 * building their own APK. The button is then simply absent.
 */
// A plain class, not a value class: Dagger's generated Java factories cannot
// call the mangled constructor an inline class compiles to.
data class GoogleAuthConfig(val serverClientId: String) {
    val isConfigured: Boolean get() = serverClientId.isNotBlank()
}

/** What came back from the account sheet. */
sealed interface GoogleCredentialResult {
    data class Success(val idToken: String) : GoogleCredentialResult

    /** No Google account on the device at all. */
    data object NoAccount : GoogleCredentialResult

    /** The sheet was dismissed. Not an error — say nothing, show nothing. */
    data object Cancelled : GoogleCredentialResult

    /** Play services missing or refusing; the message is for debug builds. */
    data class Unavailable(val cause: Throwable) : GoogleCredentialResult
}

/**
 * Reads a Google ID token from the accounts already signed in on this device.
 *
 * Two passes on purpose. The first asks only for accounts that have used
 * unefy before, which is the quiet one-tap case. When there are none, Android
 * answers [NoCredentialException] rather than showing anything, and the second
 * pass opens the full picker — otherwise a first-time user with three Google
 * accounts on the phone would see nothing happen at all.
 */
@Singleton
class GoogleCredentialClient @Inject constructor(
    private val config: GoogleAuthConfig,
) {
    /**
     * @param activityContext must be an Activity — Credential Manager shows UI.
     * @param nonce the value the backend issued; Google copies it into the token.
     */
    suspend fun idToken(activityContext: Context, nonce: String): GoogleCredentialResult {
        val manager = CredentialManager.create(activityContext)

        val returning = request(
            manager,
            activityContext,
            nonce,
            filterByAuthorizedAccounts = true,
        )
        if (returning !is GoogleCredentialResult.NoAccount) return returning

        return request(manager, activityContext, nonce, filterByAuthorizedAccounts = false)
    }

    private suspend fun request(
        manager: CredentialManager,
        activityContext: Context,
        nonce: String,
        filterByAuthorizedAccounts: Boolean,
    ): GoogleCredentialResult {
        val option = GetGoogleIdOption.Builder()
            .setServerClientId(config.serverClientId)
            .setFilterByAuthorizedAccounts(filterByAuthorizedAccounts)
            .setNonce(nonce)
            // Only meaningful in the first pass, and only with exactly one
            // previously used account: it signs straight in without a tap.
            .setAutoSelectEnabled(filterByAuthorizedAccounts)
            .build()

        return try {
            val response = manager.getCredential(
                context = activityContext,
                request = GetCredentialRequest.Builder().addCredentialOption(option).build(),
            )
            response.credential.toResult()
        } catch (e: NoCredentialException) {
            GoogleCredentialResult.NoAccount
        } catch (e: GetCredentialCancellationException) {
            GoogleCredentialResult.Cancelled
        } catch (e: GetCredentialException) {
            GoogleCredentialResult.Unavailable(e)
        }
    }

    private fun androidx.credentials.Credential.toResult(): GoogleCredentialResult {
        if (this !is CustomCredential || type != GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL) {
            return GoogleCredentialResult.Unavailable(
                IllegalStateException("Unexpected credential type: $type"),
            )
        }
        return try {
            GoogleCredentialResult.Success(GoogleIdTokenCredential.createFrom(data).idToken)
        } catch (e: GoogleIdTokenParsingException) {
            GoogleCredentialResult.Unavailable(e)
        }
    }
}

/**
 * The whole sign-in, end to end — sheet plus token exchange.
 *
 * Split out from [ApiError] because two of the outcomes are not failures the
 * user should be told about in the same tone: a dismissed sheet deserves
 * silence, and "no Google account on this phone" is advice, not an error.
 */
sealed interface GoogleSignInOutcome {
    data class Success(val session: Session) : GoogleSignInOutcome

    data object Cancelled : GoogleSignInOutcome

    data object NoAccount : GoogleSignInOutcome

    /** This build ships no client id, or the server has none configured. */
    data object NotConfigured : GoogleSignInOutcome

    data class Failure(val error: ApiError) : GoogleSignInOutcome

    /** Credential Manager itself could not run. */
    data class Unavailable(val cause: Throwable) : GoogleSignInOutcome
}
