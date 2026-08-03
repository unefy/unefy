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
        /**
         * What the backend returned for the active [filter]. Already filtered —
         * the chips reload rather than narrow what is on screen, because the
         * pages loaded so far are not the whole ledger.
         */
        val entries: List<DuesEntry>,
        val filter: DuesFilter,
        val isRefreshing: Boolean = false,
        /** A refresh that failed, so the screen can say so and then forget it. */
        val refreshFailed: Boolean = false,
        /** A further page is on its way, so the list can show a footer. */
        val isLoadingMore: Boolean = false,
    ) : DuesUiState

    data class Failure(val error: ApiError) : DuesUiState
}

/**
 * The chips, as the backend's own status values.
 *
 * `OPEN` maps to the literal `open` rather than to "everything not paid", which
 * is what the old client-side filter meant. That quietly counted cancelled dues
 * as outstanding — a due that was written off is not money anyone is waiting for.
 */
enum class DuesFilter(val apiValue: String?) {
    ALL(null),
    OPEN(DuesStatus.OPEN.apiValue),
    PAID(DuesStatus.PAID.apiValue),
}

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

    fun refresh() = load(showRefreshing = true, keepOnFailure = true)

    fun onMessageShown() = _uiState.update { state ->
        (state as? DuesUiState.Content)?.copy(refreshFailed = false) ?: state
    }

    /** Appends the next page of entries, under the filter that is active. */
    fun loadMore() {
        if (!pages.start()) return
        _uiState.update { state ->
            (state as? DuesUiState.Content)?.copy(isLoadingMore = true) ?: state
        }

        moreInFlight = viewModelScope.launch {
            when (val result = repository.list(page = pages.next, status = filter.apiValue)) {
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

    /**
     * Reloads under the new filter. A round trip, where this used to be a local
     * list operation — the cost of the chips telling the truth about a ledger
     * that does not fit in memory.
     */
    fun onFilterChange(value: DuesFilter) {
        if (value == filter) return
        filter = value
        // The chip flips immediately; the rows follow. keepOnFailure is false on
        // purpose — rows from the old filter under a chip that says "offen" would
        // be worse than the error screen.
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
        val current = _uiState.value
        if (showRefreshing && current is DuesUiState.Content) {
            _uiState.value = current.copy(isRefreshing = true, refreshFailed = false)
        } else {
            _uiState.value = DuesUiState.Loading
        }
        pages.reset()

        viewModelScope.launch {
            // Both calls in flight at once — the summary is not derived from the
            // page of entries, so waiting for one before the other is wasted time.
            val entriesDeferred = async { repository.list(page = 1, status = filter.apiValue) }
            val summaryDeferred = async { repository.summary() }

            when (val entries = entriesDeferred.await()) {
                is ApiResult.Success -> {
                    pages.advance(entries.meta)
                    _uiState.value = DuesUiState.Content(
                        summary = (summaryDeferred.await() as? ApiResult.Success)?.data,
                        entries = entries.data,
                        filter = filter,
                    )
                }

                // A refresh that fails keeps the list it already has and says so
                // in a snackbar. Replacing loaded content with a full-screen
                // error because the connection dropped for a second is worse
                // than showing something a minute out of date.
                is ApiResult.Failure -> {
                    val keep = if (keepOnFailure) _uiState.value as? DuesUiState.Content else null
                    _uiState.value = keep?.copy(isRefreshing = false, refreshFailed = true)
                        ?: DuesUiState.Failure(entries.error)
                }
            }
        }
    }
}
