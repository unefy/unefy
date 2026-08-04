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
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
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
        /** Registration ids a board removal is in flight for — the row locks. */
        val removing: Set<String> = emptySet(),
        /** A board action failed; shown once as a snackbar, then handed back. */
        val actionFailed: Boolean = false,
    ) : EventDetailUiState

    data class Failure(val error: ApiError) : EventDetailUiState
}

/**
 * The board's add sheet: who could be put on the event.
 *
 * Its own state rather than part of [EventDetailUiState] because the sheet has
 * a life of its own — it opens, searches and closes without the event
 * underneath changing.
 */
data class MemberPickerState(
    val visible: Boolean = false,
    val query: String = "",
    val options: List<MemberOption> = emptyList(),
    val loading: Boolean = false,
    /** The member a register call is in flight for — that row locks. */
    val pendingMemberId: String? = null,
    val failed: Boolean = false,
)

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

    private val removing = MutableStateFlow<Set<String>>(emptySet())
    private val actionFailed = MutableStateFlow(false)

    private val _picker = MutableStateFlow(MemberPickerState())
    val picker: StateFlow<MemberPickerState> = _picker.asStateFlow()

    val uiState: StateFlow<EventDetailUiState> = combine(
        eventId.flatMapLatest { id -> id?.let(repository::byIdStream) ?: flowOf(null) },
        remote,
        busy,
        connectivity.isOnline(),
        combine(removing, actionFailed) { r, f -> r to f },
    ) { mirrored, result, isBusy, online, (removingIds, failed) ->
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
                removing = removingIds,
                actionFailed = failed,
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

    // ------------------------------------------------------------------
    // Board actions — the add sheet and per-row removal.
    // ------------------------------------------------------------------

    fun openPicker() {
        _picker.value = MemberPickerState(visible = true, loading = true)
        viewModelScope.launch { loadOptions("") }
    }

    fun dismissPicker() {
        _picker.value = MemberPickerState()
    }

    fun setPickerQuery(query: String) {
        _picker.update { it.copy(query = query, loading = true) }
        viewModelScope.launch { loadOptions(query) }
    }

    private suspend fun loadOptions(query: String) {
        val result = repository.memberOptions(query.takeIf { it.isNotBlank() })
        _picker.update { state ->
            when {
                // A newer query or a closed sheet — this answer is history.
                !state.visible || state.query != query -> state
                result is ApiResult.Success ->
                    state.copy(options = result.data, loading = false, failed = false)
                else -> state.copy(loading = false, failed = true)
            }
        }
    }

    /**
     * Registers [option] on behalf of the board. The confirmed row is written
     * locally first — with the id the server just returned and the status the
     * capacity dictates — so the sheet and the list agree even if the
     * follow-up re-fetch dies; the re-fetch then supplies the server's view.
     */
    fun pickMember(option: MemberOption) {
        val id = eventId.value ?: return
        if (_picker.value.pendingMemberId != null) return
        _picker.update { it.copy(pendingMemberId = option.id) }

        viewModelScope.launch {
            when (val result = repository.registerMember(id, option.id)) {
                is ApiResult.Success -> {
                    (remote.value as? ApiResult.Success)?.data?.let { current ->
                        val waitlisted = current.event.isFull
                        remote.value = ApiResult.Success(
                            current.copy(
                                registrations = current.registrations + EventRegistration(
                                    id = result.data,
                                    memberId = option.id,
                                    memberName = option.name,
                                    status = if (waitlisted) "waitlist" else "registered",
                                    note = null,
                                ),
                                event = current.event.copy(
                                    registeredCount = current.event.registeredCount +
                                        if (waitlisted) 0 else 1,
                                ),
                            ),
                        )
                    }
                    (repository.detail(id) as? ApiResult.Success)?.let { remote.value = it }
                }

                is ApiResult.Failure -> actionFailed.value = true
            }
            _picker.update { it.copy(pendingMemberId = null) }
        }
    }

    /**
     * Removes one registration. Locally first for the same reason as
     * [pickMember]; the re-fetch afterwards is what surfaces a promoted
     * waitlist entry.
     */
    fun removeRegistration(registrationId: String) {
        val id = eventId.value ?: return
        if (registrationId in removing.value) return
        removing.update { it + registrationId }

        viewModelScope.launch {
            when (repository.removeRegistration(id, registrationId)) {
                is ApiResult.Success -> {
                    (remote.value as? ApiResult.Success)?.data?.let { current ->
                        val removed = current.registrations.find { it.id == registrationId }
                        remote.value = ApiResult.Success(
                            current.copy(
                                registrations = current.registrations
                                    .filterNot { it.id == registrationId },
                                event = current.event.copy(
                                    registeredCount = (
                                        current.event.registeredCount -
                                            if (removed?.isWaitlisted == false) 1 else 0
                                        ).coerceAtLeast(0),
                                ),
                            ),
                        )
                    }
                    (repository.detail(id) as? ApiResult.Success)?.let { remote.value = it }
                }

                is ApiResult.Failure -> actionFailed.value = true
            }
            removing.update { it - registrationId }
        }
    }

    fun onActionFailedShown() {
        actionFailed.value = false
    }

    private companion object {
        const val SUBSCRIPTION_GRACE_MS = 5_000L
    }
}
