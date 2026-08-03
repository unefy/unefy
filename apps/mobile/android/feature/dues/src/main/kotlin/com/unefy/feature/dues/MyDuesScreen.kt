package com.unefy.feature.dues

import androidx.compose.foundation.layout.RowScope
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
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

/**
 * The caller's own dues.
 *
 * A separate ViewModel rather than a flag on [DuesViewModel]: the club-wide
 * summary is administrative and would 403 here, so the two screens genuinely
 * load different things. Same presentation, different question.
 */
@HiltViewModel
class MyDuesViewModel @Inject constructor(
    private val repository: DuesRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow<DuesUiState>(DuesUiState.Loading)
    val uiState: StateFlow<DuesUiState> = _uiState.asStateFlow()

    private var filter = DuesFilter.ALL

    private val pages = PageTracker()

    /** Cancelled by [load], so a late page cannot append to a reloaded list. */
    private var moreInFlight: Job? = null

    /** Cancelled by the next [load] — see [DuesViewModel.loadInFlight]. */
    private var loadInFlight: Job? = null

    init {
        load()
    }

    fun retry() = load()

    fun refresh() = load(showRefreshing = true, keepOnFailure = true)

    fun onMessageShown() = _uiState.update { state ->
        (state as? DuesUiState.Content)?.copy(refreshFailed = false) ?: state
    }

    fun loadMore() {
        if (!pages.start()) return
        _uiState.update { state ->
            (state as? DuesUiState.Content)?.copy(isLoadingMore = true) ?: state
        }

        moreInFlight = viewModelScope.launch {
            when (val result = repository.mine(page = pages.next, status = filter.apiValue)) {
                is ApiResult.Success -> {
                    pages.advance(result.meta)
                    _uiState.update { state ->
                        (state as? DuesUiState.Content)?.copy(
                            entries = state.entries + result.data,
                            isLoadingMore = false,
                        ) ?: state
                    }
                }

                is ApiResult.Failure -> {
                    pages.fail()
                    _uiState.update { state ->
                        (state as? DuesUiState.Content)
                            ?.copy(isLoadingMore = false, refreshFailed = true) ?: state
                    }
                }
            }
        }
    }

    /** Reloads under the new filter — see [DuesViewModel.onFilterChange]. */
    fun onFilterChange(value: DuesFilter) {
        if (value == filter) return
        filter = value
        _uiState.update { state ->
            (state as? DuesUiState.Content)?.copy(filter = value) ?: state
        }
        load(showRefreshing = true, keepOnFailure = false)
    }

    private fun load(
        /** Keep the rows on screen with the refresh indicator, rather than clearing them. */
        showRefreshing: Boolean = false,
        /** Keep the rows if the call fails, instead of showing the error screen. */
        keepOnFailure: Boolean = false,
    ) {
        moreInFlight?.cancel()
        loadInFlight?.cancel()
        val current = _uiState.value
        if (showRefreshing && current is DuesUiState.Content) {
            _uiState.value = current.copy(isRefreshing = true, refreshFailed = false)
        } else {
            _uiState.value = DuesUiState.Loading
        }
        pages.reset()

        val requested = filter
        loadInFlight = viewModelScope.launch {
            when (val result = repository.mine(page = 1, status = requested.apiValue)) {
                is ApiResult.Success -> {
                    pages.advance(result.meta)
                    _uiState.value = DuesUiState.Content(
                        // No summary: /dues/summary is club-wide and board-only.
                        summary = null,
                        entries = result.data,
                        filter = requested,
                    )
                }

                is ApiResult.Failure -> {
                    val keep = if (keepOnFailure) _uiState.value as? DuesUiState.Content else null
                    _uiState.value = keep?.copy(isRefreshing = false, refreshFailed = true)
                        ?: DuesUiState.Failure(result.error)
                }
            }
        }
    }
}

@Composable
fun MyDuesRoute(
    actions: @Composable RowScope.() -> Unit = {},
    viewModel: MyDuesViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    DuesScreen(
        state = state,
        titleRes = R.string.dues_mine_title,
        showMemberName = false,
        actions = actions,
        onFilterChange = viewModel::onFilterChange,
        onRetry = viewModel::retry,
        onRefresh = viewModel::refresh,
        onLoadMore = viewModel::loadMore,
        onMessageShown = viewModel::onMessageShown,
    )
}
