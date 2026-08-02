package com.unefy.feature.events

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.model.Event
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
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

    init {
        load()
    }

    fun retry() = load()

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

    private fun load(quiet: Boolean = false) {
        if (!quiet) _uiState.value = EventsUiState.Loading
        viewModelScope.launch {
            _uiState.value = when (val result = repository.list()) {
                is ApiResult.Success -> {
                    val now = clock.nowIso()
                    val (past, upcoming) = result.data.partition { it.startsAt < now }
                    EventsUiState.Content(
                        upcoming = upcoming.sortedBy { it.startsAt },
                        past = past.sortedByDescending { it.startsAt },
                        now = now,
                    )
                }

                is ApiResult.Failure -> EventsUiState.Failure(result.error)
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
