package com.unefy.feature.dues

import androidx.compose.foundation.layout.RowScope
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.unefy.core.network.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
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

    init {
        load()
    }

    fun retry() = load()

    fun refresh() = load(refreshing = true)

    fun onMessageShown() = _uiState.update { state ->
        (state as? DuesUiState.Content)?.copy(refreshFailed = false) ?: state
    }

    fun onFilterChange(value: DuesFilter) {
        filter = value
        _uiState.value = (_uiState.value as? DuesUiState.Content)?.copy(filter = value)
            ?: _uiState.value
    }

    private fun load(refreshing: Boolean = false) {
        val current = _uiState.value
        if (refreshing && current is DuesUiState.Content) {
            _uiState.value = current.copy(isRefreshing = true, refreshFailed = false)
        } else {
            _uiState.value = DuesUiState.Loading
        }

        viewModelScope.launch {
            _uiState.value = when (val result = repository.mine()) {
                is ApiResult.Success -> DuesUiState.Content(
                    // No summary: /dues/summary is club-wide and board-only.
                    summary = null,
                    entries = result.data,
                    filter = filter,
                )

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
        onMessageShown = viewModel::onMessageShown,
    )
}
