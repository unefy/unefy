package com.unefy.app

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.unefy.app.ui.login.LoginRoute
import com.unefy.core.auth.AuthRepository
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.ClubRole
import com.unefy.core.model.Session
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

@HiltViewModel
class SessionViewModel @Inject constructor(
    private val authRepository: AuthRepository,
) : ViewModel() {

    /**
     * Null while the encrypted store is still being read. Rendering the login
     * screen during that window would flash it at an already-signed-in user.
     */
    val isSignedIn: StateFlow<Boolean?> = authRepository.isSignedIn
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(STOP_TIMEOUT_MS), null)

    val session: StateFlow<Session?> = authRepository.session
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(STOP_TIMEOUT_MS), null)

    /**
     * Clearing the encrypted store flips [isSignedIn], and UnefyRoot swaps back
     * to the login screen on its own. No navigation call is needed — the session
     * remains the single source of truth for which screen is shown.
     */
    fun signOut() {
        viewModelScope.launch { authRepository.signOut() }
    }

    private companion object {
        const val STOP_TIMEOUT_MS = 5_000L
    }
}

/**
 * Theme and appearance live above the session switch so a theme change does not
 * unmount the screen underneath it.
 */
@Composable
fun UnefyRoot(viewModel: SessionViewModel = hiltViewModel()) {
    val signedIn by viewModel.isSignedIn.collectAsStateWithLifecycle()
    val session by viewModel.session.collectAsStateWithLifecycle()

    UnefyTheme {
        when (signedIn) {
            null -> Box(Modifier.fillMaxSize())
            false -> LoginRoute()
            true -> MainNavigation(
                clubName = session?.tenant?.name,
                accountEmail = session?.user?.email,
                accountName = session?.user?.name,
                role = ClubRole.fromApi(session?.role),
                onSignOut = viewModel::signOut,
            )
        }
    }
}
