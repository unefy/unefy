package com.unefy.feature.events

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.model.Event
import com.unefy.core.model.EventDetail
import com.unefy.core.model.EventRegistration
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import com.unefy.core.sync.ConnectivityMonitor
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

sealed interface EventDetailUiState {
    data object Loading : EventDetailUiState

    data class Content(
        val event: Event,
        /** Everyone on the event, waitlist included. Empty until the fetch lands. */
        val registrations: List<EventRegistration>,
        /**
         * Whether the online detail has answered. Only then may the screen show
         * a capacity pill, the sign-up control or the participant list — the
         * mirror alone does not know any of it, and not showing beats showing
         * "0 von 40" that is really "no data".
         */
        val detailLoaded: Boolean,
        val online: Boolean,
        /** A registration call is in flight — the button locks, see the list. */
        val busy: Boolean,
        /** The instant the state was built, so the deadline can be judged. */
        val now: String,
    ) : EventDetailUiState

    data class Failure(val error: ApiError) : EventDetailUiState
}

/**
 * One event, from the two sources the list also lives off.
 *
 * The mirror carries what the event *is* and has it without a network, so the
 * screen opens instantly and still works offline. The single-event endpoint
 * contributes what the sync payload never has: whether *this member* is on it,
 * how many others are, and their names. Merged rather than raced — the mirror
 * stays authoritative for its fields because a sync can update them while the
 * screen is open, and the fetched copy only fills the enrichment on top.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class EventDetailViewModel @Inject constructor(
    private val repository: EventsRepository,
    private val clock: EventsClock,
    connectivity: ConnectivityMonitor,
) : ViewModel() {

    private val eventId = MutableStateFlow<String?>(null)

    /** The server's answer; null until the fetch lands, kept on toggle failure. */
    private val remote = MutableStateFlow<ApiResult<EventDetail>?>(null)

    private val busy = MutableStateFlow(false)

    val uiState: StateFlow<EventDetailUiState> = combine(
        eventId.flatMapLatest { id -> id?.let(repository::byIdStream) ?: flowOf(null) },
        remote,
        busy,
        connectivity.isOnline(),
    ) { mirrored, result, isBusy, online ->
        val fetched = (result as? ApiResult.Success)?.data
        val event = mirrored?.let { base ->
            fetched?.event?.let { enriched ->
                base.copy(
                    isRegistered = enriched.isRegistered,
                    registeredCount = enriched.registeredCount,
                    competitionName = enriched.competitionName,
                )
            } ?: base
        } ?: fetched?.event

        when {
            event != null -> EventDetailUiState.Content(
                event = event,
                registrations = fetched?.registrations.orEmpty(),
                detailLoaded = fetched != null,
                online = online,
                busy = isBusy,
                now = clock.nowIso(),
            )
            // Only a failure when there is nothing at all to show — replacing a
            // mirrored event with an error screen because the connection dropped
            // would be a worse screen than one without a participant list.
            result is ApiResult.Failure -> EventDetailUiState.Failure(result.error)
            else -> EventDetailUiState.Loading
        }
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(SUBSCRIPTION_GRACE_MS),
        initialValue = EventDetailUiState.Loading,
    )

    fun load(id: String) {
        if (eventId.value == id) return
        eventId.value = id
        remote.value = null

        viewModelScope.launch { remote.value = repository.detail(id) }
    }

    /**
     * Toggles the caller's own registration, then re-fetches the detail: the
     * participant list and the count must show the world the call just created,
     * not wait the six seconds the safety lag keeps the mirror behind.
     */
    fun toggleRegistration() {
        val id = eventId.value ?: return
        val current = (remote.value as? ApiResult.Success)?.data ?: return
        if (!busy.compareAndSet(expect = false, update = true)) return

        viewModelScope.launch {
            try {
                val result = if (current.event.isRegistered) {
                    repository.unregister(id)
                } else {
                    repository.register(id)
                }
                if (result is ApiResult.Success) {
                    // The confirmed result first, locally: even if the re-fetch
                    // below fails, the button must hold the state the server
                    // just acknowledged rather than invite a second, doomed tap.
                    val wasRegistered = current.event.isRegistered
                    // Registering into a full event lands on the waitlist, and
                    // waitlisted names do not count — the pill must not claim
                    // one more than the server will report.
                    val delta = when {
                        wasRegistered -> -1
                        current.event.isFull -> 0
                        else -> 1
                    }
                    remote.value = ApiResult.Success(
                        current.copy(
                            event = current.event.copy(
                                isRegistered = !wasRegistered,
                                registeredCount = (current.event.registeredCount + delta)
                                    .coerceAtLeast(0),
                            ),
                        ),
                    )
                    // Then the server's view, for the participant list. A failed
                    // re-fetch keeps the local answer — enrichment a minute old
                    // beats a screen that forgets who is coming.
                    (repository.detail(id) as? ApiResult.Success)?.let { remote.value = it }
                }
            } finally {
                busy.value = false
            }
        }
    }

    private companion object {
        const val SUBSCRIPTION_GRACE_MS = 5_000L
    }
}
