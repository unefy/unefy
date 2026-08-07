package com.unefy.app.ui.login

import android.content.Context
import androidx.annotation.StringRes
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.app.BuildConfig
import com.unefy.app.R
import com.unefy.app.di.ServerUrlStore
import com.unefy.core.auth.AuthRepository
import com.unefy.core.auth.GoogleAuthConfig
import com.unefy.core.auth.GoogleSignInOutcome
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Two steps: type the address, then the code that lands in its inbox. */
enum class LoginStep { EMAIL, CODE }

data class LoginUiState(
    val email: String = "",
    val code: String = "",
    val step: LoginStep = LoginStep.EMAIL,
    val isSubmitting: Boolean = false,
    @StringRes val errorMessage: Int? = null,
    /**
     * Debug builds only. A bare "backend unreachable" is useless when the cause
     * could be a blocked cleartext connection, a wrong port or a timeout — this
     * carries the actual exception so the screen can say which.
     */
    val debugDetail: String? = null,
    /** Which backend the next request goes to. Shown at the foot of the screen. */
    val serverUrl: String = "",
    /**
     * Whether this build carries a Google client id. False hides the button
     * outright — a button that can only ever fail is worse than none.
     */
    val googleAvailable: Boolean = false,
)

private const val CODE_LENGTH = 6

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val servers: ServerUrlStore,
    googleConfig: GoogleAuthConfig,
) : ViewModel() {

    private val _uiState = MutableStateFlow(
        LoginUiState(serverUrl = servers.current(), googleAvailable = googleConfig.isConfigured),
    )
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    /**
     * Point the app at another backend.
     *
     * The code the user is part-way through was issued by the old server and is
     * meaningless to the new one, so the form goes back to the address step
     * rather than leaving a stale code in a field that will silently fail.
     */
    fun useServer(url: String) {
        if (!ServerUrlStore.isValid(url)) {
            _uiState.update { it.copy(errorMessage = R.string.login_server_invalid) }
            return
        }
        viewModelScope.launch {
            servers.set(url)
            _uiState.update {
                it.copy(
                    serverUrl = servers.current(),
                    step = LoginStep.EMAIL,
                    code = "",
                    errorMessage = null,
                    debugDetail = null,
                )
            }
        }
    }

    /** Back to the address the build shipped with. */
    fun useDefaultServer() {
        viewModelScope.launch {
            servers.reset()
            _uiState.update {
                it.copy(
                    serverUrl = servers.current(),
                    step = LoginStep.EMAIL,
                    code = "",
                    errorMessage = null,
                    debugDetail = null,
                )
            }
        }
    }

    fun onEmailChange(value: String) {
        _uiState.update { it.copy(email = value, errorMessage = null) }
    }

    fun onCodeChange(value: String) {
        val digits = value.filter(Char::isDigit).take(CODE_LENGTH)
        _uiState.update { it.copy(code = digits, errorMessage = null) }
    }

    /** Back to the address — also the way to request a fresh code. */
    fun editEmail() {
        _uiState.update {
            it.copy(step = LoginStep.EMAIL, code = "", errorMessage = null, debugDetail = null)
        }
    }

    fun submit() {
        if (_uiState.value.isSubmitting) return
        when (_uiState.value.step) {
            LoginStep.EMAIL -> requestCode()
            LoginStep.CODE -> verifyCode()
        }
    }

    private fun requestCode() {
        _uiState.update { it.copy(isSubmitting = true, errorMessage = null) }
        viewModelScope.launch {
            when (val result = authRepository.requestLoginCode(_uiState.value.email)) {
                is ApiResult.Success -> _uiState.update {
                    it.copy(isSubmitting = false, step = LoginStep.CODE, code = "")
                }

                is ApiResult.Failure -> _uiState.update {
                    it.copy(
                        isSubmitting = false,
                        errorMessage = result.error.toMessage(),
                        debugDetail = result.error.debugDetail(),
                    )
                }
            }
        }
    }

    private fun verifyCode() {
        _uiState.update { it.copy(isSubmitting = true, errorMessage = null) }
        viewModelScope.launch {
            // On success nothing is navigated here: the session flow flips and
            // UnefyApp swaps the screen. One source of truth for "signed in".
            when (
                val result = authRepository.verifyLoginCode(
                    _uiState.value.email,
                    _uiState.value.code,
                )
            ) {
                is ApiResult.Success -> Unit
                is ApiResult.Failure -> _uiState.update {
                    it.copy(
                        isSubmitting = false,
                        errorMessage = result.error.toCodeMessage(),
                        debugDetail = result.error.debugDetail(),
                    )
                }
            }
        }
    }

    /**
     * Sign in with a Google account already on the phone.
     *
     * Needs the Activity, not the application context: Credential Manager
     * shows the account sheet itself. That is the one place this app hands a
     * UI object to a ViewModel, and the alternative — an activity-result
     * dance routed back through the screen — buys nothing.
     */
    fun signInWithGoogle(activityContext: Context) {
        if (_uiState.value.isSubmitting) return
        _uiState.update { it.copy(isSubmitting = true, errorMessage = null, debugDetail = null) }
        viewModelScope.launch {
            when (val outcome = authRepository.signInWithGoogle(activityContext)) {
                // Nothing to do — the session flow flips and UnefyApp swaps
                // the screen, exactly as after a verified code.
                is GoogleSignInOutcome.Success -> Unit

                // Dismissing the sheet is a decision, not a failure.
                GoogleSignInOutcome.Cancelled -> _uiState.update { it.copy(isSubmitting = false) }

                GoogleSignInOutcome.NoAccount -> _uiState.update {
                    it.copy(isSubmitting = false, errorMessage = R.string.login_google_no_account)
                }

                GoogleSignInOutcome.NotConfigured -> _uiState.update {
                    it.copy(
                        isSubmitting = false,
                        errorMessage = R.string.login_google_unavailable,
                    )
                }

                is GoogleSignInOutcome.Unavailable -> _uiState.update {
                    it.copy(
                        isSubmitting = false,
                        errorMessage = R.string.login_google_unavailable,
                        debugDetail = if (BuildConfig.DEBUG) {
                            "${outcome.cause::class.simpleName}: ${outcome.cause.message}"
                        } else {
                            null
                        },
                    )
                }

                is GoogleSignInOutcome.Failure -> _uiState.update {
                    it.copy(
                        isSubmitting = false,
                        errorMessage = outcome.error.toGoogleMessage(),
                        debugDetail = outcome.error.debugDetail(),
                    )
                }
            }
        }
    }

    @StringRes
    private fun ApiError.toGoogleMessage(): Int = when {
        this is ApiError.Network -> R.string.login_offline
        // 412: Google vouched for the person, but the account has no club.
        this is ApiError.Http && status == NO_CLUB_STATUS -> R.string.login_no_club
        else -> R.string.login_google_failed
    }

    @StringRes
    private fun ApiError.toMessage(): Int = when (this) {
        is ApiError.Network -> R.string.login_offline
        else -> R.string.login_failed
    }

    @StringRes
    private fun ApiError.toCodeMessage(): Int = when {
        this is ApiError.Network -> R.string.login_offline
        // 412: the mailbox is proven but the account belongs to no club yet.
        this is ApiError.Http && status == NO_CLUB_STATUS -> R.string.login_no_club
        this is ApiError.Forbidden -> R.string.login_code_rejected
        else -> R.string.login_failed
    }

    private fun ApiError.debugDetail(): String? {
        if (!BuildConfig.DEBUG) return null
        val cause = when (this) {
            is ApiError.Network -> "${cause::class.simpleName}: ${cause.message}"
            is ApiError.Unknown -> "${cause::class.simpleName}: ${cause.message}"
            is ApiError.Serialization -> "Serialization: ${cause.message}"
            is ApiError.Http -> "HTTP $status ${code.orEmpty()} ${message.orEmpty()}"
            ApiError.Unauthorized -> "HTTP 401"
            ApiError.Forbidden -> "HTTP 403"
            is ApiError.NotFound -> "HTTP 404 ${code.orEmpty()}"
        }
        return "${BuildConfig.API_BASE_URL}\n$cause"
    }

    private companion object {
        const val NO_CLUB_STATUS = 412
    }
}
