package com.unefy.app.theme

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/**
 * Holds the chosen appearance for the whole shell.
 *
 * Seeded with [ThemeMode.SYSTEM] rather than a nullable: DataStore answers a
 * frame or two after the first composition, and starting at "follow the system"
 * means that window looks like the device already does — no flash of the wrong
 * scheme for someone who picked an override.
 */
@HiltViewModel
class ThemeViewModel @Inject constructor(
    private val preferences: ThemePreferences,
) : ViewModel() {

    val mode: StateFlow<ThemeMode> = preferences.mode
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(STOP_TIMEOUT_MS), ThemeMode.SYSTEM)

    fun setMode(value: ThemeMode) {
        viewModelScope.launch { preferences.setMode(value) }
    }

    private companion object {
        const val STOP_TIMEOUT_MS = 5_000L
    }
}
