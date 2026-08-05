package com.unefy.feature.attendance

import androidx.annotation.StringRes
import androidx.compose.animation.animateColor
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyListScope
// The List overload of items(); without it the Int-count one is resolved.
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.SwipeToDismissBox
import androidx.compose.material3.SwipeToDismissBoxValue
import androidx.compose.material3.Text
import androidx.compose.material3.rememberSwipeToDismissBoxState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.component.UnefyListScaffold
import com.unefy.core.designsystem.component.UnefyRowDivider
import com.unefy.core.designsystem.theme.UnefyMotion
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme

/**
 * Who is in one session — the paper list, as a screen of its own.
 *
 * Split out from under the scanner's viewfinder: with discipline, weapon and
 * round count on every row this is data entry at the range table, not scan
 * feedback, and it wants the whole screen the scanner could not give it.
 */
@Composable
fun AttendanceListRoute(
    sessionId: String,
    sessionTitle: String,
    onBack: () -> Unit,
    viewModel: AttendanceListViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    LaunchedEffect(sessionId) { viewModel.load(sessionId) }

    // A check-in can land while this screen is open — from the scanner one step
    // back, or from another supervisor's phone. Coming forward reloads.
    RefreshOnResume(viewModel::refresh)

    AttendanceListScreen(
        state = state,
        sessionTitle = sessionTitle,
        onBack = onBack,
        onRetry = viewModel::refresh,
        onUndo = viewModel::undo,
        onEditShootingDetail = viewModel::editShootingDetail,
        onDismissShootingDetail = viewModel::dismissShootingDetail,
        onSaveShootingDetail = viewModel::saveShootingDetail,
    )
}

@Composable
fun AttendanceListScreen(
    state: AttendanceListUiState,
    sessionTitle: String,
    onBack: () -> Unit = {},
    onRetry: () -> Unit = {},
    onUndo: (CheckedInEntry) -> Unit = {},
    onEditShootingDetail: (CheckedInEntry) -> Unit = {},
    onDismissShootingDetail: () -> Unit = {},
    onSaveShootingDetail: (String?, String?, Int?) -> Unit = { _, _, _ -> },
) {
    val shooting = state.shooting
    val editing = shooting?.editing
    if (shooting != null && editing != null) {
        ShootingDetailSheet(
            entry = editing,
            detail = shooting.details[editing.key],
            disciplines = shooting.disciplines,
            saving = shooting.saving,
            onSave = onSaveShootingDetail,
            onDismiss = onDismissShootingDetail,
        )
    }

    UnefyListScaffold(
        title = stringResource(R.string.attendance_list_title),
        // Which evening this is the list of. With two sessions open the title
        // alone would leave the supervisor guessing.
        subtitle = sessionTitle,
        navigationIcon = {
            IconButton(onClick = onBack) {
                Icon(
                    painter = painterResource(DesignR.drawable.ic_arrow_back),
                    contentDescription = stringResource(R.string.scanner_back),
                )
            }
        },
    ) {
        state.notice?.let { notice ->
            item("notice") { NoticeBanner(notice) }
        }

        when {
            state.loading && state.entries.isEmpty() -> attendanceSkeleton()

            state.error != null -> item("error") {
                ListMessage(
                    title = stringResource(R.string.attendance_list_error_title),
                    body = stringResource(R.string.attendance_list_error_body),
                    action = stringResource(R.string.attendance_retry) to onRetry,
                )
            }

            state.entries.isEmpty() -> item("empty") {
                ListMessage(
                    title = stringResource(R.string.attendance_list_empty_title),
                    body = stringResource(R.string.attendance_list_empty_body),
                )
            }

            else -> attendanceRows(
                state = state,
                onUndo = onUndo,
                onEditShootingDetail = onEditShootingDetail,
            )
        }
    }
}

private fun LazyListScope.attendanceRows(
    state: AttendanceListUiState,
    onUndo: (CheckedInEntry) -> Unit,
    onEditShootingDetail: (CheckedInEntry) -> Unit,
) {
    items(state.entries, key = { it.key }) { entry ->
        // Swipe, matching the rest of the app's lists. A mistap is the common
        // reason a row is here wrongly, and it wants to be undone in the same
        // gesture-and-a-half it took to create.
        val dismiss = rememberSwipeToDismissBoxState()
        LaunchedEffect(dismiss.currentValue) {
            if (dismiss.currentValue != SwipeToDismissBoxValue.Settled) onUndo(entry)
        }
        SwipeToDismissBox(
            state = dismiss,
            backgroundContent = {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(MaterialTheme.colorScheme.errorContainer),
                    contentAlignment = Alignment.CenterEnd,
                ) {
                    Text(
                        text = stringResource(R.string.scanner_undo),
                        style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                        modifier = Modifier.padding(horizontal = UnefySpacing.screen),
                    )
                }
            },
        ) {
            AttendanceRow(
                entry = entry,
                detail = state.shooting?.details?.get(entry.key),
                disciplines = state.shooting?.disciplines.orEmpty(),
                // A guest has no member record, so the server refuses a detail
                // on it; a pending row has no record id yet to hang one on.
                onEdit = if (
                    state.shooting != null && !entry.pending && entry.memberId != null
                ) {
                    { onEditShootingDetail(entry) }
                } else {
                    null
                },
            )
        }
        UnefyRowDivider()
    }
}

/**
 * The outcome of the last undo or save, above the list rather than over it.
 *
 * These are aftermath, not scan feedback: the supervisor is reading a list, and
 * a line that scrolls with it says what happened without covering a row.
 */
@Composable
private fun NoticeBanner(notice: AttendanceListNotice) {
    val (text, isError) = when (notice) {
        is AttendanceListNotice.Undone ->
            stringResource(R.string.scanner_undone, notice.memberName) to false

        is AttendanceListNotice.UndoFailed ->
            stringResource(R.string.attendance_list_undo_failed) to true

        is AttendanceListNotice.SaveFailed ->
            stringResource(R.string.shooting_save_failed) to true
    }
    Surface(
        shape = MaterialTheme.shapes.large,
        color = if (isError) {
            MaterialTheme.colorScheme.errorContainer
        } else {
            MaterialTheme.colorScheme.surfaceContainerHighest
        },
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.sm),
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium,
            color = if (isError) {
                MaterialTheme.colorScheme.onErrorContainer
            } else {
                MaterialTheme.colorScheme.onSurface
            },
            modifier = Modifier.padding(UnefySpacing.md),
        )
    }
}

@Composable
internal fun AttendanceRow(
    entry: CheckedInEntry,
    detail: ShootingDetail?,
    disciplines: List<ClubDiscipline>,
    /** Null when this row cannot carry a shooting detail — see the call site. */
    onEdit: (() -> Unit)?,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .then(
                if (onEdit != null) {
                    Modifier.clickable(
                        onClickLabel = stringResource(R.string.shooting_edit),
                        onClick = onEdit,
                    )
                } else {
                    Modifier
                }
            )
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.sm),
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = entry.memberName.ifBlank { stringResource(R.string.scanner_unknown_member) },
                style = MaterialTheme.typography.bodyLarge,
            )
            Text(
                text = stringResource(rowLabelFor(entry)),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            // Only when something was entered. An empty line under every row
            // would make the list twice as tall to say nothing.
            val summary = shootingSummary(detail, disciplines)
            if (summary != null) {
                Text(
                    text = summary,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/**
 * The three shooting fields on one line, or null when there is nothing to say.
 *
 * Short names where the club set one: "LG 10m" is what the range book prints and
 * what the supervisor recognises, and the full name would push the round count off
 * a phone screen.
 */
@Composable
private fun shootingSummary(
    detail: ShootingDetail?,
    disciplines: List<ClubDiscipline>,
): String? {
    if (detail == null) return null
    val discipline = disciplines.firstOrNull { it.id == detail.clubDisciplineId }
    val parts = listOfNotNull(
        discipline?.shortName ?: discipline?.name,
        detail.weaponCategory?.let { weaponLabel(it) },
        detail.roundsFired?.let { count ->
            pluralStringResource(R.plurals.shooting_rounds_short, count, count)
        },
    )
    return parts.joinToString(" · ").ifBlank { null }
}

/**
 * How one checked-in row describes itself.
 *
 * Three answers where there used to be two, and the third is why this is a
 * function now: a self-entry — the supervisor's own attendance — used to fall into
 * the `else` and read as "Von Hand", i.e. as a record somebody else had made. That
 * is the one thing it is not, and the whole reason the server marks it.
 *
 * "Wartet" wins over the method because for a queued row the method is still the
 * app's guess; the server has not spoken yet.
 */
@StringRes
internal fun rowLabelFor(entry: CheckedInEntry): Int = when {
    entry.pending -> R.string.scanner_row_pending
    entry.method == "self" -> R.string.scanner_row_self
    entry.method == "staff_scan" -> R.string.scanner_row_scanned
    else -> R.string.scanner_row_manual
}

@Composable
private fun ListMessage(
    title: String,
    body: String,
    action: Pair<String, () -> Unit>? = null,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(UnefySpacing.lg),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
    ) {
        Text(text = title, style = MaterialTheme.typography.titleMedium)
        Text(
            text = body,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        action?.let { (label, onClick) ->
            Button(onClick = onClick) { Text(label) }
        }
    }
}

/** Skeleton rows matched to the geometry of [AttendanceRow]. */
private fun LazyListScope.attendanceSkeleton() {
    items(SKELETON_ROWS) { AttendanceSkeletonRow() }
}

@Composable
private fun AttendanceSkeletonRow() {
    val transition = rememberInfiniteTransition(label = "skeleton")
    val color by transition.animateColor(
        initialValue = MaterialTheme.colorScheme.surfaceContainer,
        targetValue = MaterialTheme.colorScheme.surfaceContainerHighest,
        animationSpec = infiniteRepeatable(UnefyMotion.shimmer(), RepeatMode.Reverse),
        label = "skeletonColor",
    )

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.sm),
        verticalArrangement = Arrangement.spacedBy(UnefySpacing.xs),
    ) {
        Box(Modifier.width(168.dp).height(16.dp).background(color, SkeletonShape))
        Box(Modifier.width(72.dp).height(12.dp).background(color, SkeletonShape))
    }
    UnefyRowDivider()
}

private val SkeletonShape = RoundedCornerShape(6.dp)
private const val SKELETON_ROWS = 8

@Preview
@Composable
private fun AttendanceListPreview() {
    UnefyTheme {
        AttendanceListScreen(
            state = AttendanceListUiState(
                entries = listOf(
                    CheckedInEntry("r1", "m1", "Alice Example", "staff_scan", 100),
                    CheckedInEntry("r2", null, "Gast Gustav", "manual", 90),
                ),
                loading = false,
                shooting = ShootingState(
                    disciplines = listOf(ClubDiscipline("c1", "Luftgewehr", "LG 10m")),
                    details = mapOf(
                        "r1" to ShootingDetail("r1", "c1", "luftdruck", 40),
                    ),
                ),
            ),
            sessionTitle = "Übungsabend",
        )
    }
}
