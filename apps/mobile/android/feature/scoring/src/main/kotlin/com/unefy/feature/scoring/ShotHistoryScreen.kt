package com.unefy.feature.scoring

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.runtime.remember
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.unefy.core.designsystem.component.TargetCanvas
import com.unefy.core.designsystem.component.UnefyCenteredState
import com.unefy.core.designsystem.component.UnefyListScaffold
import com.unefy.core.designsystem.component.UnefyStaleBanner
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.theme.UnefySpacing
import java.time.LocalDate
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.ClubRole
import com.unefy.core.model.scoring.PlacedShot
import com.unefy.core.model.scoring.TargetGeometrySeed
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
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/** Whose series the history shows. */
enum class ShotHistoryScope { MINE, CLUB }

sealed interface ShotHistoryUiState {
    data object Loading : ShotHistoryUiState
    data class Content(
        val series: List<ShotSeries>,
        val pendingCount: Int,
        val isRefreshing: Boolean = false,
        val scope: ShotHistoryScope = ShotHistoryScope.MINE,
        /**
         * Why the club mirror is not current, if it is not. Only ever set in
         * [ShotHistoryScope.CLUB] — the personal list is a cache with its own
         * refresh, not a synced collection.
         */
        val staleBecause: ApiError? = null,
    ) : ShotHistoryUiState
}

/**
 * Recorded series — the caller's own, or the whole club's.
 *
 * The personal list reads the local queue and the cache together, so a series
 * recorded two minutes ago in a basement is visible immediately and looks no
 * different from one the server already has, apart from a "not sent" marker.
 *
 * The club list reads the board-only mirror instead. Two separate sources rather
 * than one filtered query: the personal history has to work for every account,
 * and it cannot depend on a collection most accounts are not allowed to sync.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class ShotHistoryViewModel @Inject constructor(
    private val repository: ScoringRepository,
    private val coordinator: SyncCoordinator,
) : ViewModel() {

    private val refreshing = MutableStateFlow(false)
    private val scope = MutableStateFlow(ShotHistoryScope.MINE)

    val uiState: StateFlow<ShotHistoryUiState> =
        scope.flatMapLatest { active ->
            when (active) {
                ShotHistoryScope.MINE -> mineState()
                ShotHistoryScope.CLUB -> clubState()
            }
        }.stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5_000L),
            ShotHistoryUiState.Loading,
        )

    private fun mineState(): Flow<ShotHistoryUiState> = combine(
        repository.myHistory(),
        repository.pendingCount(),
        refreshing,
    ) { series, pending, isRefreshing ->
        ShotHistoryUiState.Content(
            series = series,
            pendingCount = pending,
            isRefreshing = isRefreshing,
            scope = ShotHistoryScope.MINE,
        )
    }

    private fun clubState(): Flow<ShotHistoryUiState> = combine(
        repository.clubHistory(),
        coordinator.status(EntrySyncCollection.COLLECTION),
        refreshing,
    ) { series, status, isRefreshing ->
        ShotHistoryUiState.Content(
            series = series,
            // The pending queue is the caller's own, whichever list is shown —
            // counting it here would claim the club has unsent series.
            pendingCount = 0,
            isRefreshing = isRefreshing,
            scope = ShotHistoryScope.CLUB,
            staleBecause = (status as? SyncStatus.Failed)?.error,
        )
    }

    init {
        reload()
    }

    fun refresh() = reload()

    /** Switching lists reloads: the mirror may be days old on this device. */
    fun setScope(next: ShotHistoryScope) {
        if (scope.value == next) return
        scope.value = next
        reload()
    }

    private fun reload() {
        // Claimed before launching, as in MembersViewModel: the pull gesture
        // fires while the finger is still moving, so three drags would
        // otherwise start three drains of the same queue.
        if (!refreshing.compareAndSet(expect = false, update = true)) return

        viewModelScope.launch {
            try {
                // Two calls, deliberately in this order: drain first so anything
                // queued is on the server before the refresh reads back the
                // authoritative list. Done in both scopes — a board member
                // looking at the club list still wants their own bench's series
                // to have arrived.
                repository.drainQueue()
                repository.refreshHistory()
                if (scope.value == ShotHistoryScope.CLUB) {
                    coordinator.syncNow(EntrySyncCollection.COLLECTION)
                }
            } finally {
                refreshing.value = false
            }
        }
    }
}

@Composable
fun ShotHistoryRoute(
    onRecord: () -> Unit,
    role: ClubRole = ClubRole.UNKNOWN,
    onOpenSeries: (String) -> Unit = {},
    actions: @Composable androidx.compose.foundation.layout.RowScope.() -> Unit = {},
    viewModel: ShotHistoryViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    ShotHistoryScreen(
        state = state,
        actions = actions,
        // The server refuses the club collection to anyone below board, so the
        // mirror is empty for them anyway. Hiding the switch as well keeps them
        // out of a list that would only ever be blank.
        canSeeClub = role.canAdminister,
        onRecord = onRecord,
        onOpenSeries = onOpenSeries,
        onRefresh = viewModel::refresh,
        onScopeChange = viewModel::setScope,
    )
}

@Composable
fun ShotHistoryScreen(
    state: ShotHistoryUiState,
    actions: @Composable androidx.compose.foundation.layout.RowScope.() -> Unit = {},
    onRecord: () -> Unit = {},
    onOpenSeries: (String) -> Unit = {},
    onRefresh: () -> Unit = {},
    canSeeClub: Boolean = false,
    onScopeChange: (ShotHistoryScope) -> Unit = {},
) {
    // Read once per composition rather than per heading: "today" is the same
    // for every row, and asking the clock in a loop is how a list ends up
    // straddling midnight inconsistently.
    val today = remember { LocalDate.now() }

    UnefyListScaffold(
        title = stringResource(R.string.history_title),
        actions = actions,
        isRefreshing = (state as? ShotHistoryUiState.Content)?.isRefreshing == true,
        onRefresh = onRefresh,
        banner = {
            val stale = (state as? ShotHistoryUiState.Content)?.staleBecause
            UnefyStaleBanner(
                visible = stale != null,
                text = stringResource(
                    if (stale is ApiError.Network) {
                        DesignR.string.stale_offline
                    } else {
                        DesignR.string.stale_generic
                    },
                ),
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = onRecord) {
                Icon(
                    painter = painterResource(DesignR.drawable.ic_add),
                    contentDescription = stringResource(R.string.history_record),
                )
            }
        },
    ) {
        when (state) {
            is ShotHistoryUiState.Loading ->
                item { UnefyCenteredState(title = stringResource(R.string.history_title)) }

            is ShotHistoryUiState.Content -> {
                if (canSeeClub) {
                    item {
                        ScopeSwitch(
                            scope = state.scope,
                            onScopeChange = onScopeChange,
                            modifier = Modifier.padding(
                                horizontal = UnefySpacing.screen,
                                vertical = UnefySpacing.sm,
                            ),
                        )
                    }
                }

                if (state.pendingCount > 0) {
                    item {
                        Text(
                            text = pluralStringResource(
                                R.plurals.history_pending_count,
                                state.pendingCount,
                                state.pendingCount,
                            ),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(
                                horizontal = UnefySpacing.screen,
                                vertical = UnefySpacing.sm,
                            ),
                        )
                    }
                }

                if (state.series.isEmpty()) {
                    item {
                        UnefyCenteredState(
                            title = stringResource(R.string.history_empty),
                            body = stringResource(R.string.history_empty_action),
                            action = {
                                Button(onClick = onRecord) {
                                    Text(stringResource(R.string.history_record))
                                }
                            },
                        )
                    }
                } else {
                    // Grouped by the day they were shot. A training evening
                    // produces a run of series minutes apart, and reading them
                    // as one flat list means re-reading the date on every row to
                    // work out where one session ended and the next began.
                    // Insertion order is kept, so the newest day stays on top.
                    val byDay = state.series.groupBy { recordedDay(it.recordedAt) }
                    byDay.forEach { (day, series) ->
                        if (day != null) {
                            item(key = "day-$day") {
                                DayHeading(day, today = today)
                            }
                        }
                        items(series, key = { it.id }) { entry ->
                            SeriesRow(entry, onClick = { onOpenSeries(entry.id) })
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SeriesRow(series: ShotSeries, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.sm),
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.md),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // A thumbnail of the actual hit pattern: the point of the whole feature
        // is that a series is a picture, not a number.
        series.geometry?.let { geometry ->
            TargetCanvas(
                geometry = geometry,
                shots = series.shots,
                modifier = Modifier.size(56.dp),
            )
        }

        Column(Modifier.weight(1f)) {
            Text(
                text = stringResource(R.string.history_rings, series.total),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                // Whose series it is comes first. The screen is called "my
                // series" but a board member records for anybody, and a list
                // that does not say whose shots these are is unreadable the
                // moment two people have been entered.
                text = listOfNotNull(
                    series.memberLabel?.takeIf { it.isNotBlank() },
                    formatRecordedTime(series.recordedAt),
                    series.discipline,
                ).joinToString(" · "),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (series.pending) {
                Text(
                    text = stringResource(R.string.history_pending),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/**
 * Mine / club. A segmented row rather than a filter chip: the two are mutually
 * exclusive and one of them is always on, which is exactly what this control
 * means and what a chip does not.
 */
@Composable
private fun ScopeSwitch(
    scope: ShotHistoryScope,
    onScopeChange: (ShotHistoryScope) -> Unit,
    modifier: Modifier = Modifier,
) {
    val options = listOf(
        ShotHistoryScope.MINE to R.string.history_scope_mine,
        ShotHistoryScope.CLUB to R.string.history_scope_club,
    )
    SingleChoiceSegmentedButtonRow(modifier = modifier.fillMaxWidth()) {
        options.forEachIndexed { index, (option, label) ->
            SegmentedButton(
                selected = scope == option,
                onClick = { onScopeChange(option) },
                shape = SegmentedButtonDefaults.itemShape(index = index, count = options.size),
                label = { Text(stringResource(label)) },
            )
        }
    }
}

@Preview
@Composable
private fun ShotHistoryPreview() {
    UnefyTheme {
        ShotHistoryScreen(
            state = ShotHistoryUiState.Content(
                pendingCount = 1,
                series = listOf(
                    ShotSeries(
                        id = "1",
                        memberId = "m1",
                        memberLabel = "Max Test",
                        discipline = "GK Pistole 25m",
                        targetTypeSlug = TargetGeometrySeed.PRECISION_25M.slug,
                        caliberMm = 9.0,
                        total = 87,
                        innerTens = 2,
                        groupingMm = 64.0,
                        shots = listOf(
                            PlacedShot("a", 0.02, -0.03, 10),
                            PlacedShot("b", -0.14, 0.09, 9),
                        ),
                        recordedAt = "2026-08-05T18:30:00Z",
                        notes = null,
                        pending = true,
                    ),
                ),
            ),
        )
    }
}

/**
 * The day a run of series belongs to.
 *
 * Today and yesterday are named rather than dated: those are the two a shooter
 * is actually looking for after a session, and "Heute" is recognised faster than
 * a date they then have to compare against the calendar.
 */
@Composable
private fun DayHeading(day: LocalDate, today: LocalDate) {
    val label = when (day) {
        today -> stringResource(R.string.history_day_today)
        today.minusDays(1) -> stringResource(R.string.history_day_yesterday)
        else -> formatDay(day)
    }
    Text(
        text = label,
        style = MaterialTheme.typography.titleSmall,
        fontWeight = FontWeight.SemiBold,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(
            start = UnefySpacing.screen,
            end = UnefySpacing.screen,
            top = UnefySpacing.md,
            bottom = UnefySpacing.xs,
        ),
    )
}
