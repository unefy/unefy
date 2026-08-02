package com.unefy.feature.events

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.model.Event
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

sealed interface EventsUiState {
    data object Loading : EventsUiState

    /**
     * Split rather than one list: "what is coming up" is the question a member
     * opens this screen with, and past events answer a different one.
     */
    data class Content(
        val upcoming: List<Event>,
        val past: List<Event>,
        /** The instant the list was built, so rows can judge deadlines. */
        val now: String,
        /** Event ids with a registration call in flight, so the row can lock. */
        val pending: Set<String> = emptySet(),
        val isRefreshing: Boolean = false,
        /** A refresh that failed, so the screen can say so and then forget it. */
        val refreshFailed: Boolean = false,
        /** A further page is on its way, so the list can show a footer. */
        val isLoadingMore: Boolean = false,
    ) : EventsUiState

    data class Failure(val error: ApiError) : EventsUiState
}

@HiltViewModel
class EventsViewModel @Inject constructor(
    private val repository: EventsRepository,
    private val clock: EventsClock,
) : ViewModel() {

    private val _uiState = MutableStateFlow<EventsUiState>(EventsUiState.Loading)
    val uiState: StateFlow<EventsUiState> = _uiState.asStateFlow()

    // Two streams, because they run away from each other in time: upcoming
    // ascending from now, past descending from now. One paged stream cannot be
    // both, and the screen shows both at once.
    private val upcomingPages = PageTracker()
    private val pastPages = PageTracker()

    /** The instant both streams are anchored to, held so pages stay consistent. */
    private var anchor: String = ""

    /** Cancelled by [load], so a late page cannot append to a reloaded list. */
    private var moreInFlight: Job? = null

    init {
        load()
    }

    fun retry() = load()

    fun refresh() = load(refreshing = true)

    fun onMessageShown() = _uiState.update { state ->
        (state as? EventsUiState.Content)?.copy(refreshFailed = false) ?: state
    }

    /**
     * Extends whichever stream is still running: upcoming until it is exhausted,
     * then past. That is the order the screen renders them in, so it is the
     * order the user reaches the end of.
     */
    fun loadMore() {
        val upcoming = upcomingPages.start()
        if (!upcoming && !pastPages.start()) return
        val tracker = if (upcoming) upcomingPages else pastPages

        _uiState.update { state ->
            (state as? EventsUiState.Content)?.copy(isLoadingMore = true) ?: state
        }

        moreInFlight = viewModelScope.launch {
            val result = repository.list(
                page = tracker.next,
                startsAfter = if (upcoming) anchor else null,
                startsBefore = if (upcoming) null else anchor,
                newestFirst = !upcoming,
            )

            when (result) {
                is ApiResult.Success -> {
                    tracker.advance(result.meta)
                    _uiState.update { state ->
                        val content = state as? EventsUiState.Content ?: return@update state
                        if (upcoming) {
                            content.copy(
                                upcoming = content.upcoming + result.data,
                                isLoadingMore = false,
                            )
                        } else {
                            content.copy(past = content.past + result.data, isLoadingMore = false)
                        }
                    }
                }

                is ApiResult.Failure -> {
                    tracker.fail()
                    _uiState.update { state ->
                        (state as? EventsUiState.Content)
                            ?.copy(isLoadingMore = false, refreshFailed = true) ?: state
                    }
                }
            }
        }
    }

    /**
     * Toggles the caller's own registration.
     *
     * The row locks while the call is in flight rather than flipping
     * optimistically: a full event answers with an error, and a button that
     * says "registered" and then takes it back is worse than one that waits.
     */
    fun toggleRegistration(event: Event) {
        val current = _uiState.value as? EventsUiState.Content ?: return
        if (event.id in current.pending) return
        _uiState.value = current.copy(pending = current.pending + event.id)

        viewModelScope.launch {
            val result = if (event.isRegistered) {
                repository.unregister(event.id)
            } else {
                repository.register(event.id)
            }
            when (result) {
                is ApiResult.Success -> load(quiet = true)
                is ApiResult.Failure -> _uiState.update { state ->
                    // Keep the list, drop the lock: the row returns to its old
                    // state so the user can see nothing happened and retry.
                    (state as? EventsUiState.Content)?.copy(pending = state.pending - event.id)
                        ?: state
                }
            }
        }
    }

    private fun load(quiet: Boolean = false, refreshing: Boolean = false) {
        moreInFlight?.cancel()
        val current = _uiState.value
        when {
            refreshing && current is EventsUiState.Content ->
                _uiState.value = current.copy(isRefreshing = true, refreshFailed = false)

            !quiet -> _uiState.value = EventsUiState.Loading
        }

        val now = clock.nowIso()
        anchor = now
        upcomingPages.reset()
        pastPages.reset()

        viewModelScope.launch {
            // Both windows at once: neither is derived from the other, so
            // fetching them in sequence would only add a round trip.
            val upcomingCall = async {
                repository.list(page = 1, startsAfter = now, newestFirst = false)
            }
            val pastCall = async {
                repository.list(page = 1, startsBefore = now, newestFirst = true)
            }
            val upcoming = upcomingCall.await()
            val past = pastCall.await()

            _uiState.value = if (upcoming is ApiResult.Success && past is ApiResult.Success) {
                upcomingPages.advance(upcoming.meta)
                pastPages.advance(past.meta)
                // Already ordered by the backend: ascending from now, descending
                // from now. Sorting again here would only hide a mismatch.
                EventsUiState.Content(upcoming = upcoming.data, past = past.data, now = now)
            } else {
                // A refresh that fails keeps the list it already has and says so
                // in a snackbar. Replacing loaded content with a full-screen
                // error because the connection dropped for a second is worse
                // than showing something a minute out of date.
                // pending is cleared too: this path also runs after a successful
                // registration, and a row left locked by a failed reload can
                // never be tapped again.
                val error = (upcoming as? ApiResult.Failure)?.error
                    ?: (past as ApiResult.Failure).error
                (_uiState.value as? EventsUiState.Content)
                    ?.copy(isRefreshing = false, refreshFailed = true, pending = emptySet())
                    ?: EventsUiState.Failure(error)
            }
        }
    }
}

/**
 * Injected so the upcoming/past split is testable. ISO-8601 instants in UTC sort
 * lexicographically, which is why a string comparison is correct here.
 */
fun interface EventsClock {
    fun nowIso(): String
}
