package com.unefy.feature.dues

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.model.DuesEntry
import com.unefy.core.model.DuesStatus
import com.unefy.core.model.DuesSummary
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import com.unefy.core.sync.SyncCoordinator
import com.unefy.core.sync.SyncStatus
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

sealed interface DuesUiState {
    data object Loading : DuesUiState

    data class Content(
        /** Null offline or before the aggregate has loaded — the header hides. */
        val summary: DuesSummary?,
        /**
         * The rows for the active [filter]. On the board screen this is a SQL
         * filter over the local mirror; on MyDues it is what the backend
         * returned — either way already filtered, never narrowed on screen.
         */
        val entries: List<DuesEntry>,
        val filter: DuesFilter,
        val isRefreshing: Boolean = false,
        /** A refresh that failed (MyDues only — the mirror uses [staleBecause]). */
        val refreshFailed: Boolean = false,
        /** A further page is on its way (MyDues only — the mirror has no pages). */
        val isLoadingMore: Boolean = false,
        /**
         * Why the mirror is not current, if it is not (board screen only). A
         * standing fact, not an event: clears itself on the next successful sync.
         */
        val staleBecause: ApiError? = null,
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

@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class DuesViewModel @Inject constructor(
    private val repository: DuesRepository,
    private val coordinator: SyncCoordinator,
) : ViewModel() {

    private val filter = MutableStateFlow(DuesFilter.ALL)
    private val refreshing = MutableStateFlow(false)

    /**
     * The club-wide totals, online-only by decision: one implementation of the
     * money arithmetic, on the server. Null hides the header — offline the list
     * stays and the totals simply are not claimed.
     */
    private val summary = MutableStateFlow<DuesSummary?>(null)

    /**
     * Filter and rows together, from one flow — a chip tap must never pair the
     * new chip with the old rows for a frame. The filter runs in SQL over the
     * mirror; a chip change is a local re-query, not a round trip, which is why
     * the old in-flight-request race simply no longer exists here.
     */
    private val filtered = filter.flatMapLatest { f ->
        repository.stream(f.apiValue).map { f to it }
    }

    val uiState: StateFlow<DuesUiState> = repository.hasSynced()
        .distinctUntilChanged()
        .flatMapLatest { hasSynced -> if (hasSynced) contentState() else preSyncState() }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(SUBSCRIPTION_GRACE_MS),
            initialValue = DuesUiState.Loading,
        )

    init {
        viewModelScope.launch { loadSummary() }
    }

    private fun contentState(): Flow<DuesUiState> = combine(
        filtered,
        summary,
        coordinator.status(DuesSyncCollection.COLLECTION),
        refreshing,
    ) { (activeFilter, entries), totals, status, isRefreshing ->
        DuesUiState.Content(
            summary = totals,
            entries = entries,
            filter = activeFilter,
            isRefreshing = isRefreshing,
            staleBecause = (status as? SyncStatus.Failed)?.error,
        )
    }

    private fun preSyncState(): Flow<DuesUiState> =
        coordinator.status(DuesSyncCollection.COLLECTION).map { status ->
            when {
                // A plain member may not mirror the ledger; the coordinator
                // latches the refusal, and this screen reports it as what it is.
                status == SyncStatus.NotPermitted -> DuesUiState.Failure(ApiError.Forbidden)
                status is SyncStatus.Failed -> DuesUiState.Failure(status.error)
                else -> DuesUiState.Loading
            }
        }

    fun retry() = syncNow()

    fun refresh() = syncNow()

    /** A local re-query over the mirror — no request, no race, no reload. */
    fun onFilterChange(value: DuesFilter) {
        filter.value = value
    }

    private fun syncNow() {
        // Claimed before launching — see MembersViewModel: the pull gesture
        // fires on drag, so three drags would otherwise start three drains.
        if (!refreshing.compareAndSet(expect = false, update = true)) return

        viewModelScope.launch {
            try {
                // The mirror and the aggregate together: the header should match
                // the rows it sits above.
                val drain = launch { coordinator.syncNow(DuesSyncCollection.COLLECTION) }
                loadSummary()
                drain.join()
            } finally {
                refreshing.value = false
            }
        }
    }

    private suspend fun loadSummary() {
        (repository.summary() as? ApiResult.Success)?.let { summary.value = it.data }
    }

    private companion object {
        const val SUBSCRIPTION_GRACE_MS = 5_000L
    }
}
