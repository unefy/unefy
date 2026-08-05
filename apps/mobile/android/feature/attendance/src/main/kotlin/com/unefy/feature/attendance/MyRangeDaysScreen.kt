package com.unefy.feature.attendance

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyListScope
// The List overload of items(); without it the Int-count one is resolved.
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuAnchorType
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Surface
import androidx.compose.material3.SwipeToDismissBox
import androidx.compose.material3.SwipeToDismissBoxValue
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.material3.rememberSwipeToDismissBoxState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.component.UnefyListScaffold
import com.unefy.core.designsystem.component.UnefyRowDivider
import com.unefy.core.designsystem.theme.UnefyFormat
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

/**
 * The member's own range history — the self-kept half of the §14 proof.
 *
 * Club evenings appear read-only; what belongs to the member is the external
 * entry, a visit to some other range with nobody there to attest it. The row
 * says so ("Selbst geführt"), the same honest language the scanner uses for a
 * self check-in — this list must never dress a claim up as an attest.
 */
@Composable
fun MyRangeDaysRoute(
    onBack: () -> Unit,
    viewModel: MyRangeDaysViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    RefreshOnResume(viewModel::refresh)
    MyRangeDaysScreen(
        state = state,
        onBack = onBack,
        onRetry = viewModel::refresh,
        onOpenForm = viewModel::openForm,
        onDismissForm = viewModel::dismissForm,
        onFormDateChange = viewModel::setFormDate,
        onSave = viewModel::save,
        onDelete = viewModel::delete,
    )
}

@Composable
fun MyRangeDaysScreen(
    state: MyRangeDaysUiState,
    onBack: () -> Unit = {},
    onRetry: () -> Unit = {},
    onOpenForm: () -> Unit = {},
    onDismissForm: () -> Unit = {},
    onFormDateChange: (String) -> Unit = {},
    onSave: (
        location: String,
        clubDisciplineId: String?,
        weaponCategory: String?,
        roundsFired: Int?,
    ) -> Unit = { _, _, _, _ -> },
    onDelete: (OwnRangeDay) -> Unit = {},
) {
    state.form?.let { form ->
        SelfEntrySheet(
            form = form,
            shooting = state.shooting,
            onDateChange = onFormDateChange,
            onSave = onSave,
            onDismiss = onDismissForm,
        )
    }

    UnefyListScaffold(
        title = stringResource(R.string.range_days_title),
        navigationIcon = {
            IconButton(onClick = onBack) {
                Icon(
                    painter = painterResource(DesignR.drawable.ic_arrow_back),
                    contentDescription = stringResource(R.string.scanner_back),
                )
            }
        },
        floatingActionButton = {
            FloatingActionButton(onClick = onOpenForm) {
                Icon(
                    painter = painterResource(DesignR.drawable.ic_add),
                    contentDescription = stringResource(R.string.range_days_add),
                )
            }
        },
    ) {
        state.notice?.let { notice ->
            item("notice") { RangeDaysNoticeBanner(notice) }
        }

        when {
            state.error != null -> item("error") {
                RangeDaysMessage(
                    title = stringResource(R.string.range_days_error_title),
                    body = stringResource(R.string.range_days_error_body),
                    action = stringResource(R.string.attendance_retry) to onRetry,
                )
            }

            !state.loading && state.days.isEmpty() -> item("empty") {
                RangeDaysMessage(
                    title = stringResource(R.string.range_days_empty_title),
                    body = stringResource(R.string.range_days_empty_body),
                )
            }

            else -> rangeDayRows(state = state, onDelete = onDelete)
        }
    }
}

private fun LazyListScope.rangeDayRows(
    state: MyRangeDaysUiState,
    onDelete: (OwnRangeDay) -> Unit,
) {
    items(state.days, key = { it.id }) { day ->
        if (day.origin == "external") {
            // Only own entries can be taken back — a club evening is the
            // board's record, and swiping it away must not even be offered.
            val dismiss = rememberSwipeToDismissBoxState()
            LaunchedEffect(dismiss.currentValue) {
                if (dismiss.currentValue != SwipeToDismissBoxValue.Settled) onDelete(day)
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
            ) { RangeDayRow(day) }
        } else {
            RangeDayRow(day)
        }
        UnefyRowDivider()
    }
}

@Composable
private fun RangeDayRow(day: OwnRangeDay) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.sm),
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = day.sessionTitle
                    ?: day.externalLocation
                    ?: stringResource(R.string.range_days_untitled),
                style = MaterialTheme.typography.bodyLarge,
            )
            Text(
                text = "${UnefyFormat.date(day.occurredOn)} · " + stringResource(
                    if (day.origin == "external") {
                        R.string.range_days_self_kept
                    } else {
                        R.string.range_days_club
                    },
                ),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun RangeDaysNoticeBanner(notice: RangeDaysNotice) {
    val (text, isError) = when (notice) {
        RangeDaysNotice.Created ->
            stringResource(R.string.range_days_created) to false

        RangeDaysNotice.Certified ->
            stringResource(R.string.range_days_certified) to true

        RangeDaysNotice.DayTaken ->
            stringResource(R.string.range_days_day_taken) to false

        is RangeDaysNotice.Failed ->
            stringResource(R.string.range_days_failed) to true
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

/**
 * The entry form: day, range, and — for a shooting club — what was shot.
 *
 * One sheet for all of it, because that is the whole act: "I was at SV
 * Nachbarort yesterday, forty rounds of air rifle." Splitting the details into
 * a second step would lose them, since nothing forces anyone back.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SelfEntrySheet(
    form: SelfEntryForm,
    shooting: ShootingState?,
    onDateChange: (String) -> Unit,
    onSave: (String, String?, String?, Int?) -> Unit,
    onDismiss: () -> Unit,
) {
    var location by remember { mutableStateOf("") }
    var discipline by remember { mutableStateOf<String?>(null) }
    var weapon by remember { mutableStateOf<String?>(null) }
    var rounds by remember { mutableStateOf("") }
    var disciplinesExpanded by remember { mutableStateOf(false) }
    var datePickerOpen by remember { mutableStateOf(false) }

    if (datePickerOpen) {
        val pickerState = rememberDatePickerState(
            initialSelectedDateMillis = runCatching {
                LocalDate.parse(form.occurredOn).atStartOfDay(ZoneOffset.UTC).toInstant()
                    .toEpochMilli()
            }.getOrNull(),
        )
        DatePickerDialog(
            onDismissRequest = { datePickerOpen = false },
            confirmButton = {
                TextButton(
                    onClick = {
                        pickerState.selectedDateMillis?.let { millis ->
                            onDateChange(
                                Instant.ofEpochMilli(millis)
                                    .atZone(ZoneOffset.UTC)
                                    .toLocalDate()
                                    .toString(),
                            )
                        }
                        datePickerOpen = false
                    },
                ) { Text(stringResource(R.string.range_days_date_ok)) }
            },
            dismissButton = {
                TextButton(onClick = { datePickerOpen = false }) {
                    Text(stringResource(R.string.range_days_date_cancel))
                }
            },
        ) {
            DatePicker(state = pickerState)
        }
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
    ) {
        Column(
            modifier = Modifier
                .padding(horizontal = UnefySpacing.screen)
                .padding(bottom = UnefySpacing.lg),
            verticalArrangement = Arrangement.spacedBy(UnefySpacing.md),
        ) {
            Text(
                text = stringResource(R.string.range_days_add_title),
                style = MaterialTheme.typography.titleMedium,
            )
            Text(
                text = stringResource(R.string.range_days_add_hint),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            OutlinedTextField(
                value = UnefyFormat.date(form.occurredOn),
                onValueChange = {},
                readOnly = true,
                label = { Text(stringResource(R.string.range_days_date)) },
                trailingIcon = {
                    IconButton(onClick = { datePickerOpen = true }) {
                        Icon(
                            painter = painterResource(DesignR.drawable.ic_event),
                            contentDescription = stringResource(R.string.range_days_pick_date),
                        )
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            )

            OutlinedTextField(
                value = location,
                onValueChange = { location = it },
                label = { Text(stringResource(R.string.range_days_location)) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            if (shooting != null) {
                ExposedDropdownMenuBox(
                    expanded = disciplinesExpanded,
                    onExpandedChange = { disciplinesExpanded = it },
                ) {
                    OutlinedTextField(
                        value = shooting.disciplines.firstOrNull { it.id == discipline }?.name
                            ?: stringResource(R.string.shooting_none),
                        onValueChange = {},
                        readOnly = true,
                        label = { Text(stringResource(R.string.shooting_discipline)) },
                        trailingIcon = {
                            ExposedDropdownMenuDefaults.TrailingIcon(
                                expanded = disciplinesExpanded,
                            )
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .menuAnchor(ExposedDropdownMenuAnchorType.PrimaryNotEditable),
                    )
                    ExposedDropdownMenu(
                        expanded = disciplinesExpanded,
                        onDismissRequest = { disciplinesExpanded = false },
                    ) {
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.shooting_none)) },
                            onClick = {
                                discipline = null
                                disciplinesExpanded = false
                            },
                        )
                        shooting.disciplines.forEach { option ->
                            DropdownMenuItem(
                                text = { Text(option.name) },
                                onClick = {
                                    discipline = option.id
                                    disciplinesExpanded = false
                                },
                            )
                        }
                    }
                }

                Text(
                    text = stringResource(R.string.shooting_weapon),
                    style = MaterialTheme.typography.labelLarge,
                )
                SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
                    WEAPON_CATEGORIES.forEachIndexed { index, category ->
                        SegmentedButton(
                            selected = weapon == category,
                            onClick = { weapon = if (weapon == category) null else category },
                            shape = SegmentedButtonDefaults.itemShape(
                                index = index,
                                count = WEAPON_CATEGORIES.size,
                            ),
                            label = { Text(weaponLabel(category)) },
                        )
                    }
                }

                OutlinedTextField(
                    value = rounds,
                    onValueChange = { typed -> rounds = typed.filter { it.isDigit() }.take(6) },
                    label = { Text(stringResource(R.string.shooting_rounds)) },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            Button(
                onClick = {
                    onSave(
                        location,
                        discipline,
                        weapon,
                        rounds.takeIf { it.isNotBlank() }?.toIntOrNull(),
                    )
                },
                enabled = !form.saving && location.isNotBlank(),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    stringResource(
                        if (form.saving) R.string.shooting_saving else R.string.shooting_save,
                    ),
                )
            }
        }
    }
}

@Composable
private fun RangeDaysMessage(
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
        )
        action?.let { (label, onClick) ->
            Button(onClick = onClick) { Text(label) }
        }
    }
}

@Preview
@Composable
private fun MyRangeDaysPreview() {
    UnefyTheme {
        MyRangeDaysScreen(
            state = MyRangeDaysUiState(
                days = listOf(
                    OwnRangeDay("r1", "2026-08-04", "Übungsabend", null, "club", "staff_scan"),
                    OwnRangeDay("r2", "2026-08-02", null, "SV Nachbarort", "external", "self"),
                ),
                loading = false,
            ),
        )
    }
}
