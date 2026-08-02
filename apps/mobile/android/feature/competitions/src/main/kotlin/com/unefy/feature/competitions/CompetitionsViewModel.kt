package com.unefy.feature.competitions

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.model.Competition
import com.unefy.core.model.Scoreboard
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import com.unefy.core.network.PageTracker
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.Job
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
        /** A further page is on its way, so the list can show a footer. */
        val isLoadingMore: Boolean = false,
    ) : CompetitionsUiState

    data class Failure(val error: ApiError) : CompetitionsUiState
}

@HiltViewModel
class CompetitionsViewModel @Inject constructor(
    private val repository: CompetitionsRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow<CompetitionsUiState>(CompetitionsUiState.Loading)
    val uiState: StateFlow<CompetitionsUiState> = _uiState.asStateFlow()

    private val pages = PageTracker()

    /**
     * Cancelled by [load]: a page that lands after a reload has started would
     * append rows from the old list to the new one.
     */
    private var moreInFlight: Job? = null

    init {
        load()
    }

    fun retry() = load()

    fun refresh() = load(refreshing = true)

    fun onMessageShown() = _uiState.update { state ->
        (state as? CompetitionsUiState.Content)?.copy(refreshFailed = false) ?: state
    }

    /**
     * Appends the next page. Called from scroll position, so it is asked far
     * more often than there are pages to fetch — [PageTracker] absorbs that.
     */
    fun loadMore() {
        if (!pages.start()) return
        _uiState.update { state ->
            (state as? CompetitionsUiState.Content)?.copy(isLoadingMore = true) ?: state
        }

        moreInFlight = viewModelScope.launch {
            when (val result = repository.list(page = pages.next)) {
                is ApiResult.Success -> {
                    pages.advance(result.meta)
                    _uiState.update { state ->
                        (state as? CompetitionsUiState.Content)?.copy(
                            competitions = (state.competitions + result.data)
                                .sortedByDescending { it.startDate },
                            isLoadingMore = false,
                        ) ?: state
                    }
                }

                is ApiResult.Failure -> {
                    pages.fail()
                    _uiState.update { state ->
                        (state as? CompetitionsUiState.Content)
                            ?.copy(isLoadingMore = false, refreshFailed = true) ?: state
                    }
                }
            }
        }
    }

    private fun load(refreshing: Boolean = false) {
        moreInFlight?.cancel()
        val current = _uiState.value
        if (refreshing && current is CompetitionsUiState.Content) {
            _uiState.value = current.copy(isRefreshing = true, refreshFailed = false)
        } else {
            _uiState.value = CompetitionsUiState.Loading
        }
        pages.reset()

        viewModelScope.launch {
            _uiState.value = when (val result = repository.list(page = 1)) {
                is ApiResult.Success -> {
                    pages.advance(result.meta)
                    CompetitionsUiState.Content(
                        // Most recent first: a club looks at the current season,
                        // not at the one from four years ago. The backend orders
                        // the same way, so pages arrive already in order.
                        result.data.sortedByDescending { it.startDate },
                    )
                }

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
