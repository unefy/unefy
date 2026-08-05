package com.unefy.feature.attendance

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.auth.ClubRepository
import com.unefy.core.network.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Whether this club shoots — the gate in front of "Meine Schießtage".
 *
 * Its own tiny view model so the code screen's own one stays constructible on
 * the JVM and free of a dependency it does not use. Defaults to hidden: a club
 * that briefly has no connection loses the link for one visit, while guessing
 * the other way would show §14 vocabulary to a gymnastics club.
 */
@HiltViewModel
class ShootingModuleViewModel @Inject constructor(
    clubRepository: ClubRepository,
) : ViewModel() {

    private val _enabled = MutableStateFlow(false)
    val enabled: StateFlow<Boolean> = _enabled.asStateFlow()

    init {
        viewModelScope.launch {
            val club = (clubRepository.current() as? ApiResult.Success)?.data
            _enabled.value = club?.modules?.contains(SHOOTING_MODULE) == true
        }
    }

    private companion object {
        /** As `sports.modules` spells it — see `require_module` on the server. */
        const val SHOOTING_MODULE = "shooting"
    }
}
