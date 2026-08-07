package com.unefy.feature.scoring

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.foundation.Image
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.TextButton
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.ui.input.pointer.pointerInput
import com.unefy.core.model.scoring.TargetGeometry
import kotlinx.coroutines.withTimeoutOrNull
import androidx.compose.ui.Modifier
import android.widget.Toast
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.component.TargetCanvas
import com.unefy.core.designsystem.component.UnefyCenteredState
import com.unefy.core.designsystem.component.UnefyDetailScaffold
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.scoring.PlacedShot
import com.unefy.core.model.scoring.TargetGeometrySeed
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import com.unefy.core.network.ApiResult
import kotlinx.coroutines.launch
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn

/**
 * One recorded series, full size.
 *
 * Read-only by design. A series that has already reached the server is
 * board-only to change (`PATCH` on the entry routes), and one still in the queue
 * would need its ring values recomputed and the queued payload rewritten — a
 * deliberate V2 item rather than a half-working edit.
 */
@HiltViewModel
class SeriesDetailViewModel @Inject constructor(
    private val repository: ScoringRepository,
    private val scans: ScanStore,
) : ViewModel() {

    private var seriesId: String = ""

    /**
     * The rectified sheet this series was recorded on, if it has one.
     *
     * The photograph as it came out of the camera is stored as well but is not
     * shown: holding a finger on the marked sheet already gives a clean look at
     * it. It is kept because it is what makes a bad recognition reproducible
     * off the device, and what a better rectification could be re-run on.
     */
    fun rectified(): android.graphics.Bitmap? = scans.load(seriesId, ScanStore.Kind.RECTIFIED)

    private val _deleting = MutableStateFlow(false)
    val deleting: StateFlow<Boolean> = _deleting.asStateFlow()

    /**
     * Withdraw this series, then hand back whether it worked.
     *
     * A series already on the server needs a connection; one still queued does
     * not. Either way the caller only leaves the screen on success — a delete
     * that silently failed would look exactly like one that worked.
     */
    fun delete(onDone: (Boolean) -> Unit) {
        if (_deleting.value) return
        _deleting.value = true
        viewModelScope.launch {
            val result = repository.delete(seriesId)
            _deleting.value = false
            onDone(result is ApiResult.Success)
        }
    }

    val uiState: StateFlow<ShotSeries?> = repository.myHistory()
        .map { all -> all.firstOrNull { it.id == seriesId } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000L), null)

    fun bind(id: String) {
        seriesId = id
    }
}

@Composable
fun SeriesDetailRoute(
    seriesId: String,
    onBack: () -> Unit,
    onEdit: () -> Unit = {},
    viewModel: SeriesDetailViewModel = hiltViewModel(),
) {
    viewModel.bind(seriesId)
    val series by viewModel.uiState.collectAsStateWithLifecycle()
    // Read once per series rather than on every recomposition: these are
    // megabyte bitmaps off the filesystem.
    val rectified = remember(seriesId) { viewModel.rectified() }
    val deleting by viewModel.deleting.collectAsStateWithLifecycle()
    val context = LocalContext.current
    SeriesDetailScreen(
        series = series,
        rectified = rectified,
        onBack = onBack,
        onEdit = onEdit,
        deleting = deleting,
        onDelete = {
            viewModel.delete { ok ->
                // Only leave on success. A withdrawal that failed — no signal,
                // typically — must not look like one that worked.
                if (ok) {
                    onBack()
                } else {
                    Toast.makeText(context, R.string.detail_delete_failed, Toast.LENGTH_LONG).show()
                }
            }
        },
    )
}

@Composable
fun SeriesDetailScreen(
    series: ShotSeries?,
    rectified: android.graphics.Bitmap? = null,
    onBack: () -> Unit = {},
    onEdit: () -> Unit = {},
    onDelete: () -> Unit = {},
    deleting: Boolean = false,
) {
    var confirmingDelete by remember { mutableStateOf(false) }

    UnefyDetailScaffold(
        collapsedTitle = series?.let { stringResource(R.string.history_rings, it.total) },
        onBack = onBack,
        actions = {
            // Both live in the header rather than in the page: they act on the
            // series as a whole, not on anything you scroll to, and the page
            // below is a picture that a full-width button was cutting into.
            if (series != null) {
                IconButton(onClick = onEdit) {
                    Icon(
                        painter = painterResource(DesignR.drawable.ic_edit),
                        contentDescription = stringResource(R.string.detail_edit),
                    )
                }
                IconButton(onClick = { confirmingDelete = true }, enabled = !deleting) {
                    Icon(
                        painter = painterResource(DesignR.drawable.ic_delete),
                        contentDescription = stringResource(R.string.detail_delete),
                    )
                }
            }
        },
    ) {
        // Asked for, because it cannot be undone from the app: the series is
        // withdrawn on the server, and a mis-tap in the header would otherwise
        // take a result off a competition sheet without a word.
        if (confirmingDelete) {
            AlertDialog(
                onDismissRequest = { confirmingDelete = false },
                title = { Text(stringResource(R.string.detail_delete_title)) },
                text = { Text(stringResource(R.string.detail_delete_message)) },
                confirmButton = {
                    TextButton(
                        onClick = {
                            confirmingDelete = false
                            onDelete()
                        },
                    ) { Text(stringResource(R.string.detail_delete_confirm)) }
                },
                dismissButton = {
                    TextButton(onClick = { confirmingDelete = false }) {
                        Text(stringResource(R.string.detail_delete_cancel))
                    }
                },
            )
        }

        if (series == null) {
            UnefyCenteredState(title = stringResource(R.string.detail_missing))
            return@UnefyDetailScaffold
        }

        Column(
            modifier = Modifier.padding(horizontal = UnefySpacing.screen),
            verticalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
        ) {
            Text(
                text = stringResource(R.string.history_rings, series.total),
                style = MaterialTheme.typography.displaySmall,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                // The shooter first: a board member records for other people,
                // and a result with no name on it is the one thing this screen
                // must never show.
                text = listOfNotNull(
                    series.memberLabel?.takeIf { it.isNotBlank() },
                    formatRecordedAt(series.recordedAt),
                    series.discipline,
                    series.caliberMm?.let { stringResource(R.string.detail_caliber, it) },
                ).joinToString(" · "),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (series.pending) {
                Text(
                    text = stringResource(R.string.history_pending),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            series.geometry?.let { geometry ->
                SeriesPages(
                    geometry = geometry,
                    shots = series.shots,
                    rectified = rectified,
                )
            }

            // The per-shot list in the order they were placed: a shooter reads
            // their series as a sequence, not as a set.
            series.shots.forEachIndexed { index, shot ->
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = UnefySpacing.xs),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(
                        text = stringResource(R.string.detail_shot_number, index + 1),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        text = buildString {
                            append(shot.ring)
                            if (shot.innerTen) append(" ★")
                        },
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium,
                    )
                }
            }

            // The star was unexplained until somebody asked what it meant.
            if (series.shots.any { it.innerTen }) {
                Text(
                    text = stringResource(R.string.detail_inner_ten_legend),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            series.groupingMm?.let {
                Text(
                    text = stringResource(R.string.record_grouping, it),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Preview
@Composable
private fun SeriesDetailPreview() {
    UnefyTheme {
        SeriesDetailScreen(
            series = ShotSeries(
                id = "1",
                memberId = "m1",
                memberLabel = "Max Test",
                discipline = "GK Pistole 25m",
                targetTypeSlug = TargetGeometrySeed.PRECISION_25M.slug,
                caliberMm = 9.0,
                total = 29,
                innerTens = 1,
                groupingMm = 64.0,
                shots = listOf(
                    PlacedShot("a", 0.0, 0.0, 10, innerTen = true),
                    PlacedShot("b", 0.116, 0.0, 10),
                    PlacedShot("c", -0.3, 0.15, 9),
                ),
                recordedAt = "2026-08-05T18:30:00Z",
                notes = null,
                pending = false,
            ),
        )
    }
}

/**
 * The series as three views of the same thing, swiped through.
 *
 * The drawing first, because that is the record — clean, scored, and the same
 * for every series. The photographed sheet second, with the shots on it,
 * because that is the evidence, and because seeing the rings land on the
 * printed ones is the only check there is that the rectification was right.
 * Hold a finger on it and the markers step out of the way: a marker sits
 * exactly on the hole it marks, so the moment you want to see the hole is the
 * moment it is covered.
 *
 */
@Composable
private fun SeriesPages(
    geometry: TargetGeometry,
    shots: List<PlacedShot>,
    rectified: android.graphics.Bitmap?,
) {
    val pages = buildList {
        add(Page.DRAWING)
        if (rectified != null) add(Page.MARKED_PHOTO)
    }
    val state = rememberPagerState(pageCount = { pages.size })
    var peeking by remember { mutableStateOf(false) }

    HorizontalPager(state = state) { index ->
        when (pages[index]) {
            Page.DRAWING -> TargetCanvas(
                geometry = geometry,
                shots = shots,
                showRingValues = true,
                zoomable = true,
            )

            Page.MARKED_PHOTO -> Box(
                modifier = Modifier.pointerInput(Unit) {
                    detectTapGestures(
                        onPress = {
                            // Only once the press has lasted: a quick tap is not
                            // a request to hide anything, and a swipe has to
                            // still reach the pager.
                            val released = withTimeoutOrNull(
                                viewConfiguration.longPressTimeoutMillis,
                            ) { tryAwaitRelease() }
                            if (released == null) {
                                peeking = true
                                tryAwaitRelease()
                                peeking = false
                            }
                        },
                    )
                },
            ) {
                TargetCanvas(
                    geometry = geometry,
                    shots = if (peeking) emptyList() else shots,
                    showRingValues = true,
                    photo = rectified?.asImageBitmap(),
                    zoomable = true,
                )
            }

        }
    }

    if (pages.size > 1) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center,
        ) {
            Text(
                text = stringResource(pages[state.currentPage].label),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

private enum class Page(val label: Int) {
    DRAWING(R.string.detail_page_drawing),
    MARKED_PHOTO(R.string.detail_page_marked),
}
