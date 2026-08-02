package com.unefy.feature.dues

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.model.DuesEntry
import com.unefy.core.model.DuesStatus
import com.unefy.core.model.DuesSummary
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import com.unefy.core.network.PageTracker
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

sealed interface DuesUiState {
    data object Loading : DuesUiState

    data class Content(
        val summary: DuesSummary?,
        val entries: List<DuesEntry>,
        val filter: DuesFilter,
        val isRefreshing: Boolean = false,
        /** A refresh that failed, so the screen can say so and then forget it. */
        val refreshFailed: Boolean = false,
        /** A further page is on its way, so the list can show a footer. */
        val isLoadingMore: Boolean = false,
    ) : DuesUiState {
        val visible: List<DuesEntry>
            get() = when (filter) {
                DuesFilter.ALL -> entries
                DuesFilter.OPEN -> entries.filter { it.status != DuesStatus.PAID }
                DuesFilter.PAID -> entries.filter { it.status == DuesStatus.PAID }
            }
    }

    data class Failure(val error: ApiError) : DuesUiState
}

enum class DuesFilter { ALL, OPEN, PAID }

@HiltViewModel
class DuesViewModel @Inject constructor(
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

    /**
     * Appends the next page of entries. The filter chips work on what is loaded,
     * so "offen" narrows the pages fetched so far rather than the whole ledger —
     * the backend has no status filter on this endpoint to hand the work to.
     */
    fun loadMore() {
        if (!pages.start()) return
        _uiState.update { state ->
            (state as? DuesUiState.Content)?.copy(isLoadingMore = true) ?: state
        }

        moreInFlight = viewModelScope.launch {
            when (val result = repository.list(page = pages.next)) {
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
        // Filtering is local: the list is already in memory, so a round trip
        // would only add latency.
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
            // Both calls in flight at once — the summary is not derived from the
            // page of entries, so waiting for one before the other is wasted time.
            val entriesDeferred = async { repository.list(page = 1) }
            val summaryDeferred = async { repository.summary() }

            _uiState.value = when (val entries = entriesDeferred.await()) {
                is ApiResult.Success -> {
                    pages.advance(entries.meta)
                    DuesUiState.Content(
                        summary = (summaryDeferred.await() as? ApiResult.Success)?.data,
                        entries = entries.data,
                        filter = filter,
                    )
                }

                // A refresh that fails keeps the list it already has and says so
                // in a snackbar. Replacing loaded content with a full-screen
                // error because the connection dropped for a second is worse
                // than showing something a minute out of date.
                is ApiResult.Failure -> (_uiState.value as? DuesUiState.Content)
                    ?.copy(isRefreshing = false, refreshFailed = true)
                    ?: DuesUiState.Failure(entries.error)
            }
        }
    }
}
