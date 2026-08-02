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

    init {
        load()
    }

    fun retry() = load()

    fun refresh() = load(refreshing = true)

    fun onMessageShown() = _uiState.update { state ->
        (state as? DuesUiState.Content)?.copy(refreshFailed = false) ?: state
    }

    fun loadMore() {
        if (!pages.start()) return
        _uiState.update { state ->
            (state as? DuesUiState.Content)?.copy(isLoadingMore = true) ?: state
        }

        moreInFlight = viewModelScope.launch {
            when (val result = repository.mine(page = pages.next)) {
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

    fun onFilterChange(value: DuesFilter) {
        filter = value
        _uiState.value = (_uiState.value as? DuesUiState.Content)?.copy(filter = value)
            ?: _uiState.value
    }

    private fun load(refreshing: Boolean = false) {
        moreInFlight?.cancel()
        val current = _uiState.value
        if (refreshing && current is DuesUiState.Content) {
            _uiState.value = current.copy(isRefreshing = true, refreshFailed = false)
        } else {
            _uiState.value = DuesUiState.Loading
        }
        pages.reset()

        viewModelScope.launch {
            _uiState.value = when (val result = repository.mine(page = 1)) {
                is ApiResult.Success -> {
                    pages.advance(result.meta)
                    DuesUiState.Content(
                        // No summary: /dues/summary is club-wide and board-only.
                        summary = null,
                        entries = result.data,
                        filter = filter,
                    )
                }

                is ApiResult.Failure -> (_uiState.value as? DuesUiState.Content)
                    ?.copy(isRefreshing = false, refreshFailed = true)
                    ?: DuesUiState.Failure(result.error)
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
