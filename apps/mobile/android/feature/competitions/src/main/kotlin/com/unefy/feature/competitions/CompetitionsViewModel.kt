package com.unefy.feature.competitions

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.model.Competition
import com.unefy.core.model.Scoreboard
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

sealed interface CompetitionsUiState {
    data object Loading : CompetitionsUiState

    data class Content(
        val competitions: List<Competition>,
        val isRefreshing: Boolean = false,
        /** A refresh that failed, so the screen can say so and then forget it. */
        val refreshFailed: Boolean = false,
    ) : CompetitionsUiState

    data class Failure(val error: ApiError) : CompetitionsUiState
}

@HiltViewModel
class CompetitionsViewModel @Inject constructor(
    private val repository: CompetitionsRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow<CompetitionsUiState>(CompetitionsUiState.Loading)
    val uiState: StateFlow<CompetitionsUiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun retry() = load()

    fun refresh() = load(refreshing = true)

    fun onMessageShown() = _uiState.update { state ->
        (state as? CompetitionsUiState.Content)?.copy(refreshFailed = false) ?: state
    }

    private fun load(refreshing: Boolean = false) {
        val current = _uiState.value
        if (refreshing && current is CompetitionsUiState.Content) {
            _uiState.value = current.copy(isRefreshing = true, refreshFailed = false)
        } else {
            _uiState.value = CompetitionsUiState.Loading
        }

        viewModelScope.launch {
            _uiState.value = when (val result = repository.list()) {
                is ApiResult.Success -> CompetitionsUiState.Content(
                    // Most recent first: a club looks at the current season, not
                    // at the one from four years ago.
                    result.data.sortedByDescending { it.startDate },
                )

                // A refresh that fails keeps the list it already has and says so
                // in a snackbar. Replacing loaded content with a full-screen
                // error because the connection dropped for a second is worse
                // than showing something a minute out of date.
                is ApiResult.Failure -> (_uiState.value as? CompetitionsUiState.Content)
                    ?.copy(isRefreshing = false, refreshFailed = true)
                    ?: CompetitionsUiState.Failure(result.error)
            }
        }
    }
}

sealed interface ScoreboardUiState {
    data object Loading : ScoreboardUiState

    data class Content(
        val scoreboard: Scoreboard,
        val isRefreshing: Boolean = false,
        val refreshFailed: Boolean = false,
    ) : ScoreboardUiState

    data class Failure(val error: ApiError) : ScoreboardUiState
}

@HiltViewModel
class ScoreboardViewModel @Inject constructor(
    private val repository: CompetitionsRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow<ScoreboardUiState>(ScoreboardUiState.Loading)
    val uiState: StateFlow<ScoreboardUiState> = _uiState.asStateFlow()

    /** Remembered so [refresh] does not need the id passed in a second time. */
    private var competitionId: String? = null

    fun load(competitionId: String) {
        this.competitionId = competitionId
        load(refreshing = false)
    }

    fun refresh() = load(refreshing = true)

    fun onMessageShown() = _uiState.update { state ->
        (state as? ScoreboardUiState.Content)?.copy(refreshFailed = false) ?: state
    }

    private fun load(refreshing: Boolean) {
        val id = competitionId ?: return
        val current = _uiState.value
        if (refreshing && current is ScoreboardUiState.Content) {
            _uiState.value = current.copy(isRefreshing = true, refreshFailed = false)
        } else {
            _uiState.value = ScoreboardUiState.Loading
        }

        viewModelScope.launch {
            _uiState.value = when (val result = repository.scoreboard(id)) {
                is ApiResult.Success -> ScoreboardUiState.Content(result.data)

                is ApiResult.Failure -> (_uiState.value as? ScoreboardUiState.Content)
                    ?.copy(isRefreshing = false, refreshFailed = true)
                    ?: ScoreboardUiState.Failure(result.error)
            }
        }
    }
}
