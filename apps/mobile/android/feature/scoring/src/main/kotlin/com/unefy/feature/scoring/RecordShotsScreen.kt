package com.unefy.feature.scoring

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import kotlin.math.hypot
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.hilt.navigation.compose.hiltViewModel
import com.unefy.core.designsystem.component.InteractiveTargetCanvas
import com.unefy.core.designsystem.component.UnefyCenteredState
import com.unefy.core.designsystem.component.UnefyDetailScaffold
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.scoring.Caliber
import com.unefy.core.model.scoring.Calibers
import com.unefy.core.model.scoring.SOURCE_SCAN
import com.unefy.core.model.scoring.ShotSeriesDraft
import com.unefy.core.model.scoring.TargetGeometry
import com.unefy.core.model.scoring.TargetGeometrySeed

/**
 * Recording a series by tapping the target.
 *
 * Route/Screen split as everywhere else: the route wires Hilt and collects
 * state, the screen is pure and previewable with every callback defaulted.
 */
@Composable
fun RecordShotsRoute(
    sessionId: String?,
    discipline: String?,
    memberId: String?,
    canPickMember: Boolean,
    /** Set to correct a series that is already recorded. */
    seriesId: String? = null,
    onBack: () -> Unit,
    onSaved: () -> Unit,
    viewModel: RecordShotsViewModel = hiltViewModel(),
) {
    viewModel.start(
        sessionId = sessionId,
        discipline = discipline,
        memberId = memberId,
        canPickMember = canPickMember,
        expectedShots = null,
        seriesId = seriesId,
    )
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    // The scanner is a mode of this screen, not a destination of its own. It has
    // to hand back a Bitmap, and navigation keys carry strings — routing it
    // would mean parking the image in a singleton somewhere just to get it
    // across. Staying in the same composable keeps it a local variable.
    var scanning by remember { mutableStateOf(false) }
    if (scanning) {
        val content = state as? RecordShotsUiState.Content
        ScanTargetRoute(
            geometry = content?.draft?.geometry ?: TargetGeometrySeed.DEFAULT,
            onBack = { scanning = false },
            onAccept = { photo ->
                viewModel.onPhotoCaptured(photo)
                scanning = false
            },
        )
        return
    }

    RecordShotsScreen(
        state = state,
        calibers = viewModel.calibers,
        onBack = onBack,
        onDraftChange = viewModel::onDraftChange,
        onMemberSelected = viewModel::onMemberSelected,
        onTargetSelected = viewModel::onTargetSelected,
        onCaliberSelected = viewModel::onCaliberSelected,
        onClear = viewModel::onClearShots,
        onNextSeries = viewModel::startNextSeries,
        onScan = { scanning = true },
        onDiscardPhoto = viewModel::onPhotoDiscarded,
        newShotId = viewModel::newShotId,
        onSave = { viewModel.save { onSaved() } },
    )
}

@Composable
fun RecordShotsScreen(
    state: RecordShotsUiState,
    calibers: List<Caliber> = Calibers.ALL,
    onBack: () -> Unit = {},
    onDraftChange: (ShotSeriesDraft) -> Unit = {},
    onMemberSelected: (MemberOption) -> Unit = {},
    onTargetSelected: (TargetGeometry) -> Unit = {},
    onCaliberSelected: (Double) -> Unit = {},
    onClear: () -> Unit = {},
    onNextSeries: () -> Unit = {},
    onScan: () -> Unit = {},
    onDiscardPhoto: () -> Unit = {},
    newShotId: () -> String = { "" },
    onSave: () -> Unit = {},
) {
    UnefyDetailScaffold(
        collapsedTitle = stringResource(R.string.record_title),
        onBack = onBack,
    ) {
        when (state) {
            is RecordShotsUiState.Loading ->
                UnefyCenteredState(title = stringResource(R.string.record_loading))

            is RecordShotsUiState.Failure ->
                UnefyCenteredState(title = stringResource(R.string.record_failed))

            // The scaffold already scrolls and owns the window insets.
            // The screen padding is applied per block rather than to the whole
            // column: the target is the content, and it should use the full
            // width of the screen rather than sit inside a 16dp margin.
            is RecordShotsUiState.Content -> Column(
                verticalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
            ) {
                Column(modifier = Modifier.padding(horizontal = UnefySpacing.screen)) {
                    ScoreHeader(state)
                }

                var selectedShotId by remember { mutableStateOf<String?>(null) }

                InteractiveTargetCanvas(
                    draft = state.draft,
                    onDraftChange = onDraftChange,
                    selectedShotId = selectedShotId,
                    onSelectShot = { selectedShotId = it },
                    photo = state.photo?.asImageBitmap(),
                    newShotId = newShotId,
                )

                Column(
                    modifier = Modifier.padding(horizontal = UnefySpacing.screen),
                    verticalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
                ) {

                // A shot off the sheet has nothing to tap on the target, so it
                // needs its own way in. Without it a ten-shot series with one
                // wild shot could only be saved as nine.
                OutlinedButton(
                    onClick = { onDraftChange(state.draft.placeMiss(newShotId())) },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(stringResource(R.string.record_add_miss))
                }

                // Every shot as a row, while the series is being entered.
                // Picking one out on the target alone does not work for the two
                // that matter most: a shot off the sheet is not drawn there at
                // all, and a wrongly detected one usually sits on top of the
                // right one. In a list both are one tap away.
                ShotList(
                    draft = state.draft,
                    selectedShotId = selectedShotId,
                    onSelect = { selectedShotId = if (selectedShotId == it) null else it },
                    onDelete = {
                        onDraftChange(state.draft.remove(it))
                        if (selectedShotId == it) selectedShotId = null
                    },
                )

                Text(
                    text = stringResource(R.string.record_hint),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                if (state.selectableMembers.isNotEmpty()) {
                    ChipRow(
                        label = stringResource(R.string.record_member),
                        options = state.selectableMembers.map { it.id to it.label },
                        selectedKey = state.member?.id,
                        onSelect = { id ->
                            state.selectableMembers.firstOrNull { it.id == id }
                                ?.let(onMemberSelected)
                        },
                    )
                } else if (state.member != null && state.member.label.isNotBlank()) {
                    AssistChip(onClick = {}, label = { Text(state.member.label) })
                }

                ChipRow(
                    label = stringResource(R.string.record_target),
                    options = state.targetTypes.map { it.slug to it.name },
                    selectedKey = state.draft.geometry.slug,
                    onSelect = { slug ->
                        state.targetTypes.firstOrNull { it.slug == slug }?.let(onTargetSelected)
                    },
                )

                // Two members shooting different calibers at one sheet is normal
                // here, and the caliber moves every ring boundary by half its
                // diameter — so it is a first-class control, not a setting.
                ChipRow(
                    label = stringResource(R.string.record_caliber),
                    options = calibers.map { it.key to it.name },
                    selectedKey = calibers
                        .firstOrNull { it.diameterMm == state.draft.caliberMm }?.key,
                    onSelect = { key ->
                        calibers.firstOrNull { it.key == key }
                            ?.let { onCaliberSelected(it.diameterMm) }
                    },
                )

                // Photographing is an aid to placing shots, not a separate
                // path: the result lands under the same target and is corrected
                // the same way.
                OutlinedButton(
                    onClick = if (state.photo == null) onScan else onDiscardPhoto,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(
                        stringResource(
                            if (state.photo == null) R.string.record_scan
                            else R.string.record_discard_photo,
                        ),
                    )
                }

                Row(horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm)) {
                    Button(
                        onClick = onSave,
                        enabled = state.canSave,
                        modifier = Modifier.weight(1f),
                    ) {
                        Text(stringResource(R.string.record_save))
                    }
                    OutlinedButton(
                        onClick = onClear,
                        enabled = state.draft.shots.isNotEmpty() && !state.saving,
                    ) {
                        Text(stringResource(R.string.record_clear))
                    }
                }

                if (state.savedPending) {
                    Text(
                        text = stringResource(R.string.record_queued),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    // The same sheet, the next shooter: keeps target and session,
                    // clears the shots, forces a fresh member choice.
                    OutlinedButton(onClick = onNextSeries, modifier = Modifier.fillMaxWidth()) {
                        Text(stringResource(R.string.record_next_series))
                    }
                }

                Spacer(Modifier.height(UnefySpacing.lg))
                }
            }
        }
    }
}

@Composable
private fun ScoreHeader(state: RecordShotsUiState.Content) {
    Card(colors = CardDefaults.cardColors()) {
      Column {
        Row(
            modifier = Modifier.fillMaxWidth().padding(UnefySpacing.md),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(
                    text = state.draft.total.toString(),
                    style = MaterialTheme.typography.displaySmall,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = pluralStringResource(
                        R.plurals.record_shot_count,
                        state.draft.shots.size,
                        state.draft.shots.size,
                    ),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Column(horizontalAlignment = Alignment.End) {
                if (state.draft.innerTens > 0) {
                    Text(
                        text = stringResource(R.string.record_inner_tens, state.draft.innerTens),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
                state.draft.groupingMm?.let {
                    Text(
                        text = stringResource(R.string.record_grouping, it),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }

        // The rings in the order they were shot. They used to be printed inside
        // the markers, which only worked while those were drawn too large; a
        // 9 mm hole at true scale has no room for a digit.
        if (state.draft.shots.isNotEmpty()) {
            Text(
                text = state.draft.shots.joinToString(" · ") { it.ring.toString() },
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(
                    start = UnefySpacing.md,
                    end = UnefySpacing.md,
                    bottom = UnefySpacing.md,
                ),
            )
        }
      }
    }
}

@Composable
private fun ChipRow(
    label: String,
    options: List<Pair<String, String>>,
    selectedKey: String?,
    onSelect: (String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(UnefySpacing.xs)) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        LazyRow(horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm)) {
            items(options, key = { it.first }) { (key, text) ->
                FilterChip(
                    selected = key == selectedKey,
                    onClick = { onSelect(key) },
                    label = { Text(text) },
                )
            }
        }
    }
}

@Preview
@Composable
private fun RecordShotsPreview() {
    UnefyTheme {
        RecordShotsScreen(
            state = RecordShotsUiState.Content(
                draft = ShotSeriesDraft(
                    geometry = TargetGeometrySeed.PRECISION_25M,
                    caliberMm = 9.0,
                )
                    .place("1", 0.02, -0.03)
                    .place("2", -0.14, 0.09),
                targetTypes = TargetGeometrySeed.ALL,
                member = MemberOption("m1", "Max Test"),
                selectableMembers = emptyList(),
                expectedShots = 10,
                discipline = "GK Pistole 25m",
                sessionId = null,
                occurredOn = "2026-08-05",
            ),
        )
    }
}

@Preview
@Composable
private fun RecordShotsEmptyPreview() {
    UnefyTheme {
        RecordShotsScreen(
            state = RecordShotsUiState.Content(
                draft = ShotSeriesDraft(TargetGeometrySeed.PRECISION_25M, 9.0),
                targetTypes = TargetGeometrySeed.ALL,
                member = null,
                selectableMembers = listOf(
                    MemberOption("m1", "Max Test"),
                    MemberOption("m2", "Anna Beispiel"),
                ),
                expectedShots = null,
                discipline = null,
                sessionId = null,
                occurredOn = "2026-08-05",
            ),
        )
    }
}

/**
 * The shots of the series being entered, one row each.
 *
 * The target alone is not enough to work with: a shot that missed the sheet is
 * not drawn on it, and a wrongly detected one usually sits on top of the shot it
 * should have been. A row per shot makes both reachable — tap to highlight it on
 * the target, delete to be rid of it — and it doubles as the check that the
 * count is right before saving.
 */
@Composable
private fun ShotList(
    draft: ShotSeriesDraft,
    selectedShotId: String?,
    onSelect: (String) -> Unit,
    onDelete: (String) -> Unit,
) {
    if (draft.shots.isEmpty()) return

    Column(modifier = Modifier.fillMaxWidth()) {
        draft.shots.forEachIndexed { index, shot ->
            val selected = shot.id == selectedShotId
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onSelect(shot.id) }
                    .background(
                        if (selected) MaterialTheme.colorScheme.surfaceContainerHigh
                        else Color.Transparent,
                    )
                    .padding(vertical = UnefySpacing.xs),
                horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = stringResource(R.string.record_shot_number, index + 1),
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.width(72.dp),
                )
                Text(
                    text = when {
                        shot.isMiss -> stringResource(R.string.record_shot_off_sheet)
                        shot.source == SOURCE_SCAN -> stringResource(R.string.record_shot_detected)
                        else -> ""
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    text = if (shot.innerTen) {
                        stringResource(R.string.record_inner_ten)
                    } else {
                        shot.ring.toString()
                    },
                    style = MaterialTheme.typography.titleMedium,
                )
                // A text button, because the app ships no icon set — and on a
                // bench with cold hands a word is the safer target anyway.
                TextButton(onClick = { onDelete(shot.id) }) {
                    Text(stringResource(R.string.record_delete_shot))
                }
            }
        }
    }
}
