package com.unefy.app

import android.graphics.Color
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.LocalActivity
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.DisposableEffect
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.compose.runtime.key
import com.unefy.app.theme.ThemeViewModel
import com.unefy.app.ui.login.LoginRoute
import com.unefy.core.auth.AuthRepository
import com.unefy.core.auth.TenantOption
import com.unefy.core.network.ApiResult
import kotlinx.coroutines.flow.MutableStateFlow
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
     * Every club this account belongs to. Loaded lazily when the account menu
     * first opens — most people belong to one club, and their menu should not
     * cost a request per screen.
     */
    private val _tenants = MutableStateFlow<List<TenantOption>>(emptyList())
    val tenants: StateFlow<List<TenantOption>> = _tenants

    private var switching = false

    fun loadTenants() {
        viewModelScope.launch {
            val result = authRepository.tenants()
            // Silent on failure: the menu simply shows no switch, exactly like
            // a single-club account. Retried the next time the menu opens.
            if (result is ApiResult.Success) _tenants.value = result.data
        }
    }

    /**
     * Switches this device into another club. The session flow moves on
     * success and UnefyRoot remounts the whole shell under the new tenant —
     * no navigation call, same principle as [signOut].
     */
    fun switchTenant(tenantId: String) {
        if (switching) return
        switching = true
        viewModelScope.launch {
            try {
                if (authRepository.switchTenant(tenantId) is ApiResult.Success) {
                    _tenants.value = _tenants.value.map {
                        it.copy(isCurrent = it.id == tenantId)
                    }
                }
            } finally {
                switching = false
            }
        }
    }

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
 * Scrims behind a three-button navigation bar, for the API levels that cannot
 * draw its icons over arbitrary content. The values are the ones `enableEdgeToEdge`
 * documents; gesture navigation ignores them and stays fully transparent.
 */
private val NAV_LIGHT_SCRIM = Color.argb(0xe6, 0xFF, 0xFF, 0xFF)
private val NAV_DARK_SCRIM = Color.argb(0x80, 0x1b, 0x1b, 0x1b)

/**
 * Theme and appearance live above the session switch so a theme change does not
 * unmount the screen underneath it.
 */
@Composable
fun UnefyRoot(
    viewModel: SessionViewModel = hiltViewModel(),
    themeViewModel: ThemeViewModel = hiltViewModel(),
) {
    val signedIn by viewModel.isSignedIn.collectAsStateWithLifecycle()
    val session by viewModel.session.collectAsStateWithLifecycle()

    val tenants by viewModel.tenants.collectAsStateWithLifecycle()
    val themeMode by themeViewModel.mode.collectAsStateWithLifecycle()
    val darkTheme = themeMode.isDark(isSystemInDarkTheme())

    // The status and navigation bars are the system's, not Compose's: the clock,
    // battery and gesture pill are drawn by the system on top of our content and
    // it decides light or dark icons from what `enableEdgeToEdge` was last told.
    // MainActivity says that once, from the *system* setting — so an in-app
    // override left white icons on a light screen. Re-declaring it here, keyed on
    // the resolved theme, is what keeps the two in step.
    val activity = LocalActivity.current as? ComponentActivity
    DisposableEffect(activity, darkTheme) {
        activity?.enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.auto(
                lightScrim = Color.TRANSPARENT,
                darkScrim = Color.TRANSPARENT,
            ) { darkTheme },
            navigationBarStyle = SystemBarStyle.auto(NAV_LIGHT_SCRIM, NAV_DARK_SCRIM) { darkTheme },
        )
        onDispose {}
    }

    UnefyTheme(darkTheme = darkTheme) {
        when (signedIn) {
            null -> Box(Modifier.fillMaxSize())
            false -> LoginRoute()
            // key(): a club switch replaces the whole shell. The back stack,
            // the bar arrangement and every screen's view model belong to the
            // club they were built in and must not survive into the next one.
            true -> key(session?.tenant?.id) {
                MainNavigation(
                    clubName = session?.tenant?.name,
                    accountEmail = session?.user?.email,
                    accountName = session?.user?.name,
                    role = ClubRole.fromApi(session?.role),
                    tenants = tenants,
                    themeMode = themeMode,
                    onOpenAccountMenu = viewModel::loadTenants,
                    onSwitchTenant = viewModel::switchTenant,
                    onSelectTheme = themeViewModel::setMode,
                    onSignOut = viewModel::signOut,
                )
            }
        }
    }
}
