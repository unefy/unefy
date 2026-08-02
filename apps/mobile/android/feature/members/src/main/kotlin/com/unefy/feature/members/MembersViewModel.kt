package com.unefy.feature.members

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.model.Member
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

/**
 * UI state as a sealed hierarchy — loading, content and failure are distinct
 * states rather than a bag of nullable fields, so a screen cannot render an
 * impossible combination.
 */
sealed interface MembersUiState {
    data object Loading : MembersUiState

    data class Content(
        val members: List<Member>,
        /**
         * How many the club has, not how many are loaded. With paging those
         * differ, and the header claiming "50 Mitglieder" for a club of 300
         * would be a plain lie.
         */
        val total: Int = members.size,
        val query: String = "",
        val isRefreshing: Boolean = false,
        /** A refresh that failed, so the screen can say so and then forget it. */
        val refreshFailed: Boolean = false,
        /** A further page is on its way, so the list can show a footer. */
        val isLoadingMore: Boolean = false,
    ) : MembersUiState

    data class Failure(val error: ApiError) : MembersUiState
}

@HiltViewModel
class MembersViewModel @Inject constructor(
    private val repository: MembersRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow<MembersUiState>(MembersUiState.Loading)
    val uiState: StateFlow<MembersUiState> = _uiState.asStateFlow()

    private var query: String = ""
    private var inFlight: Job? = null

    private val pages = PageTracker()

    /**
     * Cancelled by [load]: a page that lands after a new search has started
     * would append members who do not match what was typed.
     */
    private var moreInFlight: Job? = null

    init {
        load()
    }

    fun onQueryChange(value: String) {
        query = value
        _uiState.update { current ->
            if (current is MembersUiState.Content) current.copy(query = value) else current
        }
        load(showSpinner = false)
    }

    fun refresh() = load(showSpinner = false, refreshing = true)

    fun retry() = load()

    fun onMessageShown() = _uiState.update { state ->
        (state as? MembersUiState.Content)?.copy(refreshFailed = false) ?: state
    }

    /**
     * Appends the next page of the current search. Called from scroll position,
     * so it is asked far more often than there are pages — [PageTracker]
     * absorbs that.
     */
    fun loadMore() {
        if (!pages.start()) return
        _uiState.update { state ->
            (state as? MembersUiState.Content)?.copy(isLoadingMore = true) ?: state
        }

        moreInFlight = viewModelScope.launch {
            when (val result = repository.list(page = pages.next, search = query)) {
                is ApiResult.Success -> {
                    pages.advance(result.meta)
                    _uiState.update { state ->
                        (state as? MembersUiState.Content)?.copy(
                            members = state.members + result.data,
                            isLoadingMore = false,
                        ) ?: state
                    }
                }

                is ApiResult.Failure -> {
                    pages.fail()
                    _uiState.update { state ->
                        (state as? MembersUiState.Content)
                            ?.copy(isLoadingMore = false, refreshFailed = true) ?: state
                    }
                }
            }
        }
    }

    private fun load(showSpinner: Boolean = true, refreshing: Boolean = false) {
        // A new search supersedes the previous one; without this, a slow earlier
        // response could land after a faster later one and show stale results.
        inFlight?.cancel()
        moreInFlight?.cancel()
        pages.reset()

        if (showSpinner) _uiState.value = MembersUiState.Loading
        if (refreshing) {
            _uiState.update { c ->
                if (c is MembersUiState.Content) {
                    c.copy(isRefreshing = true, refreshFailed = false)
                } else {
                    c
                }
            }
        }

        inFlight = viewModelScope.launch {
            when (val result = repository.list(page = 1, search = query)) {
                is ApiResult.Success -> {
                    pages.advance(result.meta)
                    _uiState.value = MembersUiState.Content(
                        members = result.data,
                        total = result.meta?.total ?: result.data.size,
                        query = query,
                    )
                }

                // A refresh that fails keeps the list it already has and says so
                // in a snackbar. Replacing loaded content with a full-screen
                // error because the connection dropped for a second is worse
                // than showing something a minute out of date.
                //
                // Only a refresh, though. A failed *search* must not leave the
                // previous results on screen — they do not answer what was
                // typed, and a snackbar about refreshing would not explain why.
                is ApiResult.Failure -> {
                    val keep =
                        if (refreshing) _uiState.value as? MembersUiState.Content else null
                    _uiState.value = keep?.copy(isRefreshing = false, refreshFailed = true)
                        ?: MembersUiState.Failure(result.error)
                }
            }
        }
    }
}
