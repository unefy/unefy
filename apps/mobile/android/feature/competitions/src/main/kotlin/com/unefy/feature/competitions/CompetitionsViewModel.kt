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
import kotlinx.coroutines.launch

sealed interface CompetitionsUiState {
    data object Loading : CompetitionsUiState
    data class Content(val competitions: List<Competition>) : CompetitionsUiState
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

    private fun load() {
        _uiState.value = CompetitionsUiState.Loading
        viewModelScope.launch {
            _uiState.value = when (val result = repository.list()) {
                is ApiResult.Success -> CompetitionsUiState.Content(
                    // Most recent first: a club looks at the current season, not
                    // at the one from four years ago.
                    result.data.sortedByDescending { it.startDate },
                )

                is ApiResult.Failure -> CompetitionsUiState.Failure(result.error)
            }
        }
    }
}

sealed interface ScoreboardUiState {
    data object Loading : ScoreboardUiState
    data class Content(val scoreboard: Scoreboard) : ScoreboardUiState
    data class Failure(val error: ApiError) : ScoreboardUiState
}

@HiltViewModel
class ScoreboardViewModel @Inject constructor(
    private val repository: CompetitionsRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow<ScoreboardUiState>(ScoreboardUiState.Loading)
    val uiState: StateFlow<ScoreboardUiState> = _uiState.asStateFlow()

    fun load(competitionId: String) {
        _uiState.value = ScoreboardUiState.Loading
        viewModelScope.launch {
            _uiState.value = when (val result = repository.scoreboard(competitionId)) {
                is ApiResult.Success -> ScoreboardUiState.Content(result.data)
                is ApiResult.Failure -> ScoreboardUiState.Failure(result.error)
            }
        }
    }
}
