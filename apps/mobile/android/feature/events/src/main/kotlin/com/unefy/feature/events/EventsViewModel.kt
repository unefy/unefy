package com.unefy.feature.events

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.model.Event
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import com.unefy.core.sync.ConnectivityMonitor
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
import kotlinx.coroutines.flow.drop
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

sealed interface EventsUiState {
    /** The mirror has never finished a bootstrap — see MembersUiState.Loading. */
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
        /**
         * Event ids the online overlay knows about. Only these rows may show a
         * capacity pill or a registration control — for the rest the mirror
         * simply does not know, and not showing beats showing "0 of 40" that is
         * really "no data".
         */
        val overlaid: Set<String> = emptySet(),
        /** Whether the device is online — registering needs the network. */
        val online: Boolean = false,
        val isRefreshing: Boolean = false,
        /**
         * Why the mirror is not current, if it is not. A standing fact, not an
         * event: it clears itself when the next sync succeeds.
         */
        val staleBecause: ApiError? = null,
    ) : EventsUiState

    /** Nothing mirrored, and syncing failed — the only full-screen error case. */
    data class Failure(val error: ApiError) : EventsUiState
}

/**
 * The event list from the local mirror, with the caller-specific and derived
 * fields overlaid from the network when it is there.
 *
 * The mirror carries what an event *is* — title, time, place. Whether *this
 * member* is registered and how many others are is list-endpoint enrichment the
 * sync payload never delivers, so it lives in an [EventOverlay] map fetched
 * online and merged per emission. Offline the rows render from Room and the
 * registration affordances disappear, rather than lying.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class EventsViewModel @Inject constructor(
    private val repository: EventsRepository,
    private val coordinator: SyncCoordinator,
    private val clock: EventsClock,
    connectivity: ConnectivityMonitor,
) : ViewModel() {

    private val overlay = MutableStateFlow<Map<String, EventOverlay>>(emptyMap())
    private val pending = MutableStateFlow<Set<String>>(emptySet())
    private val refreshing = MutableStateFlow(false)
    private val online = connectivity.isOnline()

    val uiState: StateFlow<EventsUiState> = repository.hasSynced()
        .distinctUntilChanged()
        .flatMapLatest { hasSynced -> if (hasSynced) contentState() else preSyncState() }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(SUBSCRIPTION_GRACE_MS),
            initialValue = EventsUiState.Loading,
        )

    init {
        viewModelScope.launch { loadOverlay() }
        // Coming back online is the moment the overlay stopped being current:
        // registrations may have happened while this device could not hear.
        viewModelScope.launch {
            online.distinctUntilChanged().drop(1).filter { it }.collect { loadOverlay() }
        }
    }

    private fun contentState(): Flow<EventsUiState> = combine(
        combine(repository.stream(), overlay) { events, entries ->
            events.map { event ->
                entries[event.id]?.let {
                    event.copy(
                        isRegistered = it.isRegistered,
                        registeredCount = it.registeredCount,
                        competitionName = it.competitionName,
                    )
                } ?: event
            } to entries.keys
        },
        pending,
        combine(coordinator.status(EventSyncCollection.COLLECTION), online) { s, o -> s to o },
        refreshing,
    ) { (events, overlaid), pendingIds, (status, isOnline), isRefreshing ->
        // Split at this moment rather than at load time — there is no load. An
        // event crossing `now` migrates on the next emission, whichever flow
        // causes it. ISO-UTC instants compare correctly as strings.
        val now = clock.nowIso()
        EventsUiState.Content(
            upcoming = events.filter { it.startsAt > now },
            past = events.filter { it.startsAt <= now }.asReversed(),
            now = now,
            pending = pendingIds,
            overlaid = overlaid,
            online = isOnline,
            isRefreshing = isRefreshing,
            staleBecause = (status as? SyncStatus.Failed)?.error,
        )
    }

    private fun preSyncState(): Flow<EventsUiState> =
        coordinator.status(EventSyncCollection.COLLECTION).map { status ->
            when {
                status == SyncStatus.NotPermitted -> EventsUiState.Failure(ApiError.Forbidden)
                status is SyncStatus.Failed -> EventsUiState.Failure(status.error)
                else -> EventsUiState.Loading
            }
        }

    fun refresh() = syncNow()

    fun retry() = syncNow()

    /**
     * Toggles the caller's own registration. Online-only by decision — the
     * confirmed result updates the overlay in place, so the button holds its
     * new state instead of reverting for the six seconds the safety lag keeps
     * the mirror behind. The settle drain catches the mirror up.
     *
     * The row locks while the call is in flight rather than flipping
     * optimistically: a full event answers with an error, and a button that
     * says "registered" and then takes it back is worse than one that waits.
     */
    fun toggleRegistration(event: Event) {
        val entry = overlay.value[event.id] ?: return
        if (event.id in pending.value) return
        pending.update { it + event.id }

        viewModelScope.launch {
            val result = if (entry.isRegistered) {
                repository.unregister(event.id)
            } else {
                repository.register(event.id)
            }
            if (result is ApiResult.Success) {
                overlay.update { current ->
                    val confirmed = current[event.id] ?: entry
                    current + (
                        event.id to confirmed.copy(
                            isRegistered = !entry.isRegistered,
                            registeredCount = (
                                confirmed.registeredCount +
                                    if (entry.isRegistered) -1 else 1
                                ).coerceAtLeast(0),
                        )
                        )
                }
            }
            // On failure the lock just drops: the row returns to its old state
            // so the user can see nothing happened and retry.
            pending.update { it - event.id }
        }
    }

    private fun syncNow() {
        // Claimed before launching — see MembersViewModel: the pull gesture
        // fires on drag, so three drags would otherwise start three drains.
        if (!refreshing.compareAndSet(expect = false, update = true)) return

        viewModelScope.launch {
            try {
                // Mirror and overlay together: the pill should match the rows.
                val drain = launch { coordinator.syncNow(EventSyncCollection.COLLECTION) }
                loadOverlay()
                drain.join()
            } finally {
                refreshing.value = false
            }
        }
    }

    private suspend fun loadOverlay() {
        // A failure keeps the previous overlay: enrichment a minute old beats
        // rows that suddenly lose their registration state.
        (repository.overlay() as? ApiResult.Success)?.let { overlay.value = it.data }
    }

    private companion object {
        const val SUBSCRIPTION_GRACE_MS = 5_000L
    }
}

/**
 * Injected so the upcoming/past split is testable. ISO-8601 instants in UTC sort
 * lexicographically, which is why a string comparison is correct here.
 */
fun interface EventsClock {
    fun nowIso(): String
}
