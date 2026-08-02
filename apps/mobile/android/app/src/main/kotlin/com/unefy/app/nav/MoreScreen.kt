package com.unefy.app.nav

import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInRoot
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.unefy.app.R
import com.unefy.core.designsystem.component.UnefyListScaffold
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.model.ClubRole
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/**
 * Owns the arrangement: what is in the bar, and the edits to it.
 *
 * The role arrives from the shell rather than being read here, because the shell
 * already has the session and a mismatch between the two would be worse than the
 * plumbing.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class NavSettingsViewModel @Inject constructor(
    private val preferences: NavPreferences,
) : ViewModel() {

    private val role = MutableStateFlow(ClubRole.UNKNOWN)

    val visible: StateFlow<List<TopLevel>> = role
        .flatMapLatest { preferences.visibleDestinations(it) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(STOP_TIMEOUT), emptyList())

    fun setRole(value: ClubRole) {
        role.value = value
    }

    fun permittedFor(value: ClubRole): List<TopLevel> = permittedDestinations(value)

    /**
     * Places a section at [index], moving it if it is already in the bar.
     *
     * One operation for adding and for reordering, because from the outside they
     * are the same gesture: drop a tile onto a slot.
     */
    fun placeAt(destination: TopLevel, index: Int) {
        val current = visible.value.toMutableList()
        current.remove(destination)
        // A full bar makes room by dropping its last section — never the one
        // just dropped in, which is what truncating afterwards would do, and
        // the gesture would appear to have done nothing.
        while (current.size >= NavPreferences.MAX_VISIBLE) {
            current.removeAt(current.lastIndex)
        }
        val target = index.coerceIn(0, current.size)
        current.add(target, destination)
        persist(current)
    }

    fun remove(destination: TopLevel) {
        val current = visible.value
        // Never empty: a bar with nothing in it strands the user on whatever
        // screen they happen to be on.
        if (current.size <= 1) return
        persist(current - destination)
    }

    private fun persist(destinations: List<TopLevel>) {
        viewModelScope.launch { preferences.setVisibleDestinations(role.value, destinations) }
    }

    private companion object {
        const val STOP_TIMEOUT = 5_000L
    }
}

/**
 * The "more" tab: every section as a tile, and the bar arranged by dragging.
 *
 * A grid rather than two lists, because here the gesture is the explanation —
 * tiles are the sections, the bar below is where they go, and dropping one on a
 * slot puts it there. Tapping a tile just opens the section: someone who only
 * wants to reach something should not have to rearrange anything first.
 */
@Composable
fun MoreRoute(
    role: ClubRole,
    onDestinationClick: (TopLevel) -> Unit,
    actions: @Composable RowScope.() -> Unit = {},
    viewModel: NavSettingsViewModel = hiltViewModel(),
) {
    viewModel.setRole(role)
    val visible by viewModel.visible.collectAsStateWithLifecycle()
    val dragState = LocalNavDragState.current
    // Only what is *not* in the bar. A section shown in both places invites the
    // question which of the two is the real one; here the grid is the shelf and
    // the bar is the bar, and dragging moves a tile between them.
    val available = viewModel.permittedFor(role).filter { it !in visible }
    val rows = available.chunked(GRID_COLUMNS)

    UnefyListScaffold(title = stringResource(R.string.nav_more), actions = actions) {
        item(key = "hint") {
            Text(
                text = if (available.isEmpty()) {
                    stringResource(R.string.nav_more_grid_empty)
                } else {
                    stringResource(R.string.nav_more_grid_hint)
                },
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(
                    horizontal = UnefySpacing.screen,
                    vertical = UnefySpacing.sm,
                ),
            )
        }

        // Chunked into rows rather than a LazyVerticalGrid: this list already
        // scrolls, and nesting a lazy grid inside it needs a fixed height that
        // could only be guessed.
        items(rows.size, key = { "row-$it" }) { rowIndex ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = UnefySpacing.sm),
                horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
            ) {
                rows[rowIndex].forEach { destination ->
                    SectionTile(
                        destination = destination,
                        dragState = dragState,
                        onTap = { onDestinationClick(destination) },
                        onDropOnBar = { index -> viewModel.placeAt(destination, index) },
                        modifier = Modifier.weight(1f),
                    )
                }
                // Keeps the last row's tiles the same width as the rest.
                repeat(GRID_COLUMNS - rows[rowIndex].size) {
                    Box(modifier = Modifier.weight(1f))
                }
            }
        }
    }
}

@Composable
private fun SectionTile(
    destination: TopLevel,
    dragState: NavDragState?,
    onTap: () -> Unit,
    onDropOnBar: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    var origin by remember { mutableStateOf(Offset.Zero) }
    val beingDragged = dragState?.dragged == destination

    Surface(
        modifier = modifier
            .aspectRatio(1f)
            .padding(UnefySpacing.xs)
            .alpha(if (beingDragged) DRAGGED_ALPHA else 1f)
            .onGloballyPositioned { origin = it.positionInRoot() }
            // clickable first, drag detector last: within one modifier chain the
            // later entry sits closer to the content and sees pointer events
            // first. Reversed, clickable competed for the press and the long-press
            // drag only started sometimes.
            .clickable(onClick = onTap)
            .pointerInput(destination, dragState) {
                if (dragState == null) return@pointerInput
                detectDragGesturesAfterLongPress(
                    // origin + local: the gesture reports tile-local offsets, the
                    // bar reports root ones, and only root works for both.
                    onDragStart = { local -> dragState.begin(destination, origin + local) },
                    onDrag = { _, amount -> dragState.moveBy(amount) },
                    onDragEnd = {
                        val index = dragState.dropIndexOrNull()
                        dragState.cancel()
                        // Dropped anywhere but the bar: nothing to do. The tile
                        // is already on the shelf.
                        index?.let(onDropOnBar)
                    },
                    onDragCancel = { dragState.cancel() },
                )
            },
        shape = MaterialTheme.shapes.large,
        color = MaterialTheme.colorScheme.surfaceContainer,
    ) {
        Column(
            modifier = Modifier.padding(UnefySpacing.sm),
            verticalArrangement = Arrangement.spacedBy(UnefySpacing.xs, Alignment.CenterVertically),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Icon(
                painter = painterResource(destination.icon),
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurface,
                modifier = Modifier.size(TILE_ICON),
            )
            Text(
                text = stringResource(destination.label),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurface,
                textAlign = TextAlign.Center,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

/** The tile that follows the finger, drawn by the shell above everything else. */
@Composable
fun NavDragGhost(destination: TopLevel) {
    Surface(
        shape = MaterialTheme.shapes.large,
        color = MaterialTheme.colorScheme.surfaceContainerHighest,
        shadowElevation = GHOST_ELEVATION,
        modifier = Modifier.size(GHOST_SIZE),
    ) {
        Box(contentAlignment = Alignment.Center) {
            Icon(
                painter = painterResource(destination.icon),
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurface,
                modifier = Modifier.size(TILE_ICON),
            )
        }
    }
}

private const val GRID_COLUMNS = 3
private val TILE_ICON = 28.dp
private val GHOST_SIZE = 56.dp
private val GHOST_ELEVATION = 8.dp
private const val DRAGGED_ALPHA = 0.3f
