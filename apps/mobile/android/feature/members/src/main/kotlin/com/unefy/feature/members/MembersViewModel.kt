package com.unefy.feature.members

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.model.Member
import com.unefy.core.network.ApiError
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

/**
 * UI state as a sealed hierarchy — loading, content and failure are distinct
 * states rather than a bag of nullable fields, so a screen cannot render an
 * impossible combination.
 */
sealed interface MembersUiState {
    /**
     * The mirror does not hold the whole collection yet, so there is genuinely
     * nothing presentable — a half-filled mirror shown as content would announce
     * part of the club as all of it.
     *
     * Distinguishable from an empty club only because the sync cursor is stored
     * in the same database as the rows: until its `bootstrapComplete` flag is
     * set this is "not yet", after it an empty mirror means "no members".
     * Without that, a first launch would show "this club has no members" while
     * the bootstrap was still running.
     */
    data object Loading : MembersUiState

    data class Content(
        val members: List<Member>,
        /**
         * How many the club has, not how many are on screen — the count comes from
         * the whole mirror, the list from the current search.
         */
        val total: Int,
        val query: String = "",
        /** A drain the user asked for, so pull-to-refresh knows when to stop. */
        val isRefreshing: Boolean = false,
        /**
         * Why the mirror is not current, if it is not.
         *
         * A standing fact rather than an event, which is what changed with the
         * mirror: there is no longer a "refresh failed" moment to show once and
         * forget, only a list that is as fresh as its last successful sync. It
         * clears itself when the next sync succeeds.
         */
        val staleBecause: ApiError? = null,
    ) : MembersUiState

    /**
     * Nothing mirrored, and syncing failed. The only case where an error replaces
     * the list — because there is no list. Once anything has been mirrored a
     * failure is a banner, never a takeover: showing a full-screen error because
     * the connection dropped for a second is worse than showing a list a minute
     * out of date.
     */
    data class Failure(val error: ApiError) : MembersUiState
}

@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class MembersViewModel @Inject constructor(
    private val repository: MembersRepository,
    private val coordinator: SyncCoordinator,
) : ViewModel() {

    private val query = MutableStateFlow("")
    private val refreshing = MutableStateFlow(false)

    /**
     * Query and result together, from one flow.
     *
     * Combining them separately would let a keystroke pair the new query with the
     * previous list for a frame, long enough to render "no matches for Müll" over
     * results that do match.
     */
    private val filtered = query.flatMapLatest { q -> repository.stream(q).map { q to it } }

    /**
     * Gated on the bootstrap having finished, and the gate is also an
     * optimisation: until then nothing observes the Room queries, so a
     * fifteen-page bootstrap commits fifteen transactions without re-running
     * the full list query and re-mapping every row after each one.
     */
    val uiState: StateFlow<MembersUiState> = repository.hasSynced()
        .distinctUntilChanged()
        .flatMapLatest { hasSynced -> if (hasSynced) contentState() else preSyncState() }
        .stateIn(
        scope = viewModelScope,
        // Survives a rotation without re-reading the database, and lets go
        // afterwards so a screen nobody is on stops observing Room.
        started = SharingStarted.WhileSubscribed(SUBSCRIPTION_GRACE_MS),
        initialValue = MembersUiState.Loading,
    )

    private fun contentState(): Flow<MembersUiState> = combine(
        filtered,
        repository.count(),
        coordinator.status(MemberSyncCollection.COLLECTION),
        refreshing,
    ) { (searched, members), total, status, isRefreshing ->
        MembersUiState.Content(
            members = members,
            total = total,
            query = searched,
            isRefreshing = isRefreshing,
            staleBecause = (status as? SyncStatus.Failed)?.error,
        )
    }

    private fun preSyncState(): Flow<MembersUiState> =
        coordinator.status(MemberSyncCollection.COLLECTION).map { status ->
            when {
                // Nothing mirrored yet. A refusal is reported as Forbidden because
                // that is what it is — this role may not read the club's member
                // list — and the screen already has wording for it.
                status == SyncStatus.NotPermitted -> MembersUiState.Failure(ApiError.Forbidden)
                status is SyncStatus.Failed -> MembersUiState.Failure(status.error)
                else -> MembersUiState.Loading
            }
        }

    /**
     * Filters the mirror.
     *
     * Everything the previous version needed here — cancelling the in-flight
     * request, resetting the pager, guarding against a slow earlier response
     * landing after a fast later one — is gone, because there is no request. The
     * list is a query over local rows, and `flatMapLatest` drops the superseded
     * one.
     */
    fun onQueryChange(value: String) {
        query.value = value
    }

    fun refresh() = syncNow()

    fun retry() = syncNow()

    private fun syncNow() {
        // Claimed here rather than inside the coroutine. Checking the flag and then
        // launching leaves a gap the whole length of the dispatcher's queue: the
        // pull gesture fires on drag, so three drags all read "not refreshing" and
        // all three start a drain before any of them has set the flag.
        if (!refreshing.compareAndSet(expect = false, update = true)) return

        viewModelScope.launch {
            try {
                coordinator.syncNow(MemberSyncCollection.COLLECTION)
            } finally {
                refreshing.value = false
            }
        }
    }

    private companion object {
        const val SUBSCRIPTION_GRACE_MS = 5_000L
    }
}
