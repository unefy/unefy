package com.unefy.feature.competitions

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.model.Competition
import com.unefy.core.model.Scoreboard
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
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

sealed interface CompetitionsUiState {
    /** The mirror has never finished a bootstrap — see MembersUiState.Loading. */
    data object Loading : CompetitionsUiState

    data class Content(
        val competitions: List<Competition>,
        val isRefreshing: Boolean = false,
        /**
         * Why the mirror is not current, if it is not. A standing fact, not an
         * event: it clears itself when the next sync succeeds.
         */
        val staleBecause: ApiError? = null,
    ) : CompetitionsUiState

    /** Nothing mirrored, and syncing failed — the only full-screen error case. */
    data class Failure(val error: ApiError) : CompetitionsUiState
}

@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class CompetitionsViewModel @Inject constructor(
    private val repository: CompetitionsRepository,
    private val coordinator: SyncCoordinator,
) : ViewModel() {

    private val refreshing = MutableStateFlow(false)

    val uiState: StateFlow<CompetitionsUiState> = repository.hasSynced()
        .distinctUntilChanged()
        .flatMapLatest { hasSynced -> if (hasSynced) contentState() else preSyncState() }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(SUBSCRIPTION_GRACE_MS),
            initialValue = CompetitionsUiState.Loading,
        )

    private fun contentState(): Flow<CompetitionsUiState> = combine(
        repository.stream(),
        coordinator.status(CompetitionSyncCollection.COLLECTION),
        refreshing,
    ) { competitions, status, isRefreshing ->
        CompetitionsUiState.Content(
            // Ordered by the DAO, newest first — a club looks at the current
            // season, not at the one from four years ago.
            competitions = competitions,
            isRefreshing = isRefreshing,
            staleBecause = (status as? SyncStatus.Failed)?.error,
        )
    }

    private fun preSyncState(): Flow<CompetitionsUiState> =
        coordinator.status(CompetitionSyncCollection.COLLECTION).map { status ->
            when {
                status == SyncStatus.NotPermitted ->
                    CompetitionsUiState.Failure(ApiError.Forbidden)
                status is SyncStatus.Failed -> CompetitionsUiState.Failure(status.error)
                else -> CompetitionsUiState.Loading
            }
        }

    fun refresh() = syncNow()

    fun retry() = syncNow()

    private fun syncNow() {
        // Claimed before launching — see MembersViewModel: the pull gesture
        // fires on drag, so three drags would otherwise start three drains.
        if (!refreshing.compareAndSet(expect = false, update = true)) return

        viewModelScope.launch {
            try {
                coordinator.syncNow(CompetitionSyncCollection.COLLECTION)
            } finally {
                refreshing.value = false
            }
        }
    }

    private companion object {
        const val SUBSCRIPTION_GRACE_MS = 5_000L
    }
}

sealed interface ScoreboardUiState {
    data object Loading : ScoreboardUiState

    data class Content(
        val scoreboard: Scoreboard,
        val isRefreshing: Boolean = false,
        val refreshFailed: Boolean = false,
    ) : ScoreboardUiState

    data class Failure(val error: ApiError) : ScoreboardUiState
}

@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class ScoreboardViewModel @Inject constructor(
    private val repository: CompetitionsRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow<ScoreboardUiState>(ScoreboardUiState.Loading)
    val uiState: StateFlow<ScoreboardUiState> = _uiState.asStateFlow()

    /** Remembered so [refresh] does not need the id passed in a second time. */
    private var competitionId: String? = null

    private val competitionIdFlow = MutableStateFlow<String?>(null)

    /**
     * The competition's disciplines, from the mirror — what the filter chips
     * offer. The scoreboard response cannot answer this: a filtered board only
     * names the discipline it was asked for.
     */
    val disciplines: StateFlow<List<String>> = competitionIdFlow
        .flatMapLatest { id -> id?.let(repository::byIdStream) ?: flowOf(null) }
        .map { it?.disciplines.orEmpty() }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(SUBSCRIPTION_GRACE_MS),
            initialValue = emptyList(),
        )

    private val _selectedDiscipline = MutableStateFlow<String?>(null)

    /** Null is the combined ranking — the view every board opens with. */
    val selectedDiscipline: StateFlow<String?> = _selectedDiscipline.asStateFlow()

    fun load(competitionId: String) {
        this.competitionId = competitionId
        competitionIdFlow.value = competitionId
        load(refreshing = false)
    }

    fun refresh() = load(refreshing = true)

    /**
     * Switches the board to one discipline (null: all). Loaded as a refresh,
     * not a reload — the old ranking stays visible under the spinner instead
     * of blinking to a blank screen for every chip tap.
     */
    fun selectDiscipline(discipline: String?) {
        if (_selectedDiscipline.value == discipline) return
        _selectedDiscipline.value = discipline
        load(refreshing = true)
    }

    fun onMessageShown() = _uiState.update { state ->
        (state as? ScoreboardUiState.Content)?.copy(refreshFailed = false) ?: state
    }

    private fun load(refreshing: Boolean) {
        val id = competitionId ?: return
        val current = _uiState.value
        if (refreshing && current is ScoreboardUiState.Content) {
            _uiState.value = current.copy(isRefreshing = true, refreshFailed = false)
        } else {
            _uiState.value = ScoreboardUiState.Loading
        }

        viewModelScope.launch {
            val requested = _selectedDiscipline.value
            val result = repository.scoreboard(id, requested)
            // Superseded by a later chip tap: a slow response for the old
            // discipline must not overwrite the board the person asked for.
            if (requested != _selectedDiscipline.value) return@launch
            _uiState.value = when (result) {
                is ApiResult.Success -> ScoreboardUiState.Content(result.data)

                is ApiResult.Failure -> (_uiState.value as? ScoreboardUiState.Content)
                    ?.copy(isRefreshing = false, refreshFailed = true)
                    ?: ScoreboardUiState.Failure(result.error)
            }
        }
    }

    private companion object {
        const val SUBSCRIPTION_GRACE_MS = 5_000L
    }
}
