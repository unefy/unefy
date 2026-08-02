package com.unefy.app.ui.login

import androidx.annotation.StringRes
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.app.BuildConfig
import com.unefy.app.R
import com.unefy.core.auth.AuthRepository
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class LoginUiState(
    val email: String = "",
    val isSubmitting: Boolean = false,
    @StringRes val errorMessage: Int? = null,
    /**
     * Debug builds only. A bare "backend unreachable" is useless when the cause
     * could be a blocked cleartext connection, a wrong port or a timeout — this
     * carries the actual exception so the screen can say which.
     */
    val debugDetail: String? = null,
)

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val authRepository: AuthRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    fun onEmailChange(value: String) {
        _uiState.update { it.copy(email = value, errorMessage = null) }
    }

    fun submit() {
        if (_uiState.value.isSubmitting) return
        _uiState.update { it.copy(isSubmitting = true, errorMessage = null) }

        viewModelScope.launch {
            // On success nothing is navigated here: the session flow flips and
            // UnefyApp swaps the screen. One source of truth for "signed in".
            when (val result = authRepository.devLogin(_uiState.value.email)) {
                is ApiResult.Success -> Unit
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

    @StringRes
    private fun ApiError.toMessage(): Int = when (this) {
        is ApiError.Network -> R.string.login_offline
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
}
