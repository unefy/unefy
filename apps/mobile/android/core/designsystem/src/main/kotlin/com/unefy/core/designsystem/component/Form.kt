package com.unefy.core.designsystem.component

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TimePicker
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.material3.rememberTimePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.unefy.core.designsystem.R
import com.unefy.core.designsystem.theme.UnefyFormat
import com.unefy.core.designsystem.theme.UnefyMotion
import com.unefy.core.designsystem.theme.UnefySpacing
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle

/**
 * The form building blocks — editable rows, not boxes.
 *
 * **Why not `OutlinedTextField`.** Material's text fields put every field in its
 * own outlined container with a label that floats into a notch on focus. That is
 * the 2014 idiom, and `docs/design-system-android.md` rules it out in as many
 * words: this design wants the "editorial, tool-like character of Linear or
 * Vercel rather than the default Material look", with "hairlines over cards for
 * dense content". A screen of boxes is neither.
 *
 * More concretely, it broke the app's own continuity. [UnefyDetailSection]
 * renders a record as label-above-value rows on hairlines; a form built from
 * outlined boxes made viewing and editing the same member look like two
 * different programs. These components deliberately match that geometry to the
 * pixel, so editing reads as the record waking up rather than as another screen.
 *
 * What carries focus without a box: the hairline under the active row thickens
 * and takes the primary colour. That satisfies the greyscale rule — in a palette
 * with no hue, a focus ring in "blue" would not be visible at all.
 */

/** The row every field is built from. Matches [UnefyDetailSection]'s geometry. */
@Composable
private fun FieldRow(
    label: String,
    required: Boolean,
    focused: Boolean,
    error: String?,
    modifier: Modifier = Modifier,
    trailing: @Composable (() -> Unit)? = null,
    value: @Composable () -> Unit,
) {
    Column(modifier = modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.sm),
            horizontalArrangement = Arrangement.spacedBy(UnefySpacing.md),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    // The label never moves and never shrinks. A floating label
                    // is animation in place of information: it hides the field's
                    // name exactly when somebody is filling it in.
                    text = if (required) "$label *" else label,
                    style = MaterialTheme.typography.labelMedium,
                    color = if (error != null) {
                        MaterialTheme.colorScheme.error
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
                )
                value()
                if (error != null) {
                    Text(
                        text = error,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
            trailing?.invoke()
        }
        HorizontalDivider(
            thickness = if (focused) FOCUS_LINE else UnefySpacing.hairline,
            color = when {
                error != null -> MaterialTheme.colorScheme.error
                focused -> MaterialTheme.colorScheme.primary
                else -> MaterialTheme.colorScheme.outlineVariant
            },
        )
    }
}

/** The focused row's hairline, thick enough to read as a caret line. */
private val FOCUS_LINE = 2.dp

/** A line of text, edited in place. */
@Composable
fun UnefyTextField(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    required: Boolean = false,
    error: String? = null,
    singleLine: Boolean = true,
    keyboardType: KeyboardType = KeyboardType.Text,
    imeAction: ImeAction = ImeAction.Next,
    placeholder: String? = null,
) {
    var focused by remember { mutableStateOf(false) }

    FieldRow(label = label, required = required, focused = focused, error = error, modifier = modifier) {
        Box {
            BasicTextField(
                value = value,
                onValueChange = onValueChange,
                modifier = Modifier
                    .fillMaxWidth()
                    .onFocusChanged { focused = it.isFocused },
                textStyle = LocalTextStyle.current.merge(
                    MaterialTheme.typography.bodyLarge.copy(
                        color = MaterialTheme.colorScheme.onSurface,
                    ),
                ),
                cursorBrush = SolidColor(MaterialTheme.colorScheme.primary),
                singleLine = singleLine,
                keyboardOptions = KeyboardOptions(
                    keyboardType = keyboardType,
                    imeAction = imeAction,
                ),
            )
            if (value.isEmpty() && placeholder != null) {
                Text(
                    text = placeholder,
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/**
 * A read-only row that opens something when tapped — a picker, a menu.
 *
 * Shared by the date and choice fields so they cannot drift apart: both are "a
 * value you pick, not type", and both must look identical to a typed row or the
 * form turns into a patchwork.
 */
@Composable
private fun PickerRow(
    label: String,
    shown: String,
    placeholder: String,
    required: Boolean,
    error: String?,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    trailing: @Composable (() -> Unit)? = null,
) {
    FieldRow(
        label = label,
        required = required,
        focused = false,
        error = error,
        modifier = modifier.clickable(onClick = onClick),
        trailing = trailing,
    ) {
        Text(
            text = shown.ifBlank { placeholder },
            style = MaterialTheme.typography.bodyLarge,
            color = if (shown.isBlank()) {
                MaterialTheme.colorScheme.onSurfaceVariant
            } else {
                MaterialTheme.colorScheme.onSurface
            },
        )
    }
}

/**
 * A date, picked rather than typed.
 *
 * [value] and [onValueChange] speak ISO-8601 (`2026-08-08`), which is what the
 * API wants and what sorts correctly; the row shows it in the device's format.
 * Typing is deliberately not offered — a birthday entered as `08.03.` in a
 * German club and read as March 8th somewhere else is the kind of bug that
 * surfaces years later.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UnefyDateField(
    label: String,
    value: String?,
    onValueChange: (String?) -> Unit,
    modifier: Modifier = Modifier,
    required: Boolean = false,
    error: String? = null,
) {
    var picking by remember { mutableStateOf(false) }
    val parsed = remember(value) { value?.let { runCatching { LocalDate.parse(it) }.getOrNull() } }

    PickerRow(
        label = label,
        shown = parsed?.format(DateTimeFormatter.ofLocalizedDate(FormatStyle.MEDIUM)).orEmpty(),
        placeholder = stringResource(R.string.form_empty),
        required = required,
        error = error,
        onClick = { picking = true },
        modifier = modifier,
    )

    if (picking) {
        val state = rememberDatePickerState(
            initialSelectedDateMillis = parsed
                ?.atStartOfDay(ZoneOffset.UTC)
                ?.toInstant()
                ?.toEpochMilli(),
        )
        DatePickerDialog(
            onDismissRequest = { picking = false },
            confirmButton = {
                TextButton(
                    onClick = {
                        onValueChange(
                            state.selectedDateMillis?.let {
                                // UTC on both sides of the trip: the picker
                                // hands back midnight UTC, and reading it in a
                                // local zone west of Greenwich would land on the
                                // day before the one that was tapped.
                                Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate()
                                    .toString()
                            },
                        )
                        picking = false
                    },
                ) { Text(stringResource(R.string.form_confirm_date)) }
            },
            dismissButton = {
                TextButton(onClick = { picking = false }) {
                    Text(stringResource(R.string.form_cancel))
                }
            },
        ) {
            DatePicker(state = state)
        }
    }
}

/**
 * A moment in time: a date and a time of day, picked in that order.
 *
 * [value] and [onValueChange] speak ISO-8601 *instants* in UTC
 * (`2026-09-01T17:00:00Z`), which is what the API stores. The pickers work in
 * the device's zone, so somebody setting a club evening for 19:00 gets 19:00
 * local wherever they are — the conversion happens here rather than being
 * argued about at every call site.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UnefyDateTimeField(
    label: String,
    value: String?,
    onValueChange: (String?) -> Unit,
    modifier: Modifier = Modifier,
    required: Boolean = false,
    error: String? = null,
) {
    var pickingDate by remember { mutableStateOf(false) }
    var pickingTime by remember { mutableStateOf(false) }

    val zoned = remember(value) {
        value?.let {
            runCatching { Instant.parse(it).atZone(ZoneId.systemDefault()) }.getOrNull()
        }
    }
    // Carried between the two dialogs: the date is chosen first, and the time
    // dialog needs it to build the instant.
    var chosenDate by remember(value) { mutableStateOf(zoned?.toLocalDate()) }

    PickerRow(
        label = label,
        shown = UnefyFormat.dateTime(value),
        placeholder = stringResource(R.string.form_empty),
        required = required,
        error = error,
        onClick = { pickingDate = true },
        modifier = modifier,
    )

    if (pickingDate) {
        val state = rememberDatePickerState(
            initialSelectedDateMillis = (chosenDate ?: LocalDate.now())
                .atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli(),
        )
        DatePickerDialog(
            onDismissRequest = { pickingDate = false },
            confirmButton = {
                TextButton(
                    onClick = {
                        chosenDate = state.selectedDateMillis?.let {
                            Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate()
                        }
                        pickingDate = false
                        // Straight on to the time: an event at "some point on
                        // the 1st" is not a thing anyone means to enter.
                        if (chosenDate != null) pickingTime = true
                    },
                ) { Text(stringResource(R.string.form_confirm_date)) }
            },
            dismissButton = {
                TextButton(onClick = { pickingDate = false }) {
                    Text(stringResource(R.string.form_cancel))
                }
            },
        ) {
            DatePicker(state = state)
        }
    }

    if (pickingTime) {
        val state = rememberTimePickerState(
            initialHour = zoned?.hour ?: DEFAULT_HOUR,
            initialMinute = zoned?.minute ?: 0,
            is24Hour = true,
        )
        AlertDialog(
            onDismissRequest = { pickingTime = false },
            confirmButton = {
                TextButton(
                    onClick = {
                        val date = chosenDate
                        if (date != null) {
                            onValueChange(
                                date.atTime(state.hour, state.minute)
                                    .atZone(ZoneId.systemDefault())
                                    .toInstant()
                                    .toString(),
                            )
                        }
                        pickingTime = false
                    },
                ) { Text(stringResource(R.string.form_confirm_date)) }
            },
            dismissButton = {
                TextButton(onClick = { pickingTime = false }) {
                    Text(stringResource(R.string.form_cancel))
                }
            },
            text = { TimePicker(state = state) },
        )
    }
}

/** One choice out of a short, fixed list. */
@Composable
fun UnefyChoiceField(
    label: String,
    options: List<UnefyChoice>,
    selectedKey: String?,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }
    val selected = options.firstOrNull { it.key == selectedKey }

    Box(modifier = modifier) {
        PickerRow(
            label = label,
            shown = selected?.label.orEmpty(),
            placeholder = stringResource(R.string.form_empty),
            required = false,
            error = null,
            onClick = { expanded = true },
        )
        // Anchored to the row rather than an ExposedDropdownMenuBox: that
        // component drags its own outlined text field along, which is the thing
        // this file exists to avoid.
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { option ->
                DropdownMenuItem(
                    text = { Text(option.label) },
                    onClick = {
                        onSelect(option.key)
                        expanded = false
                    },
                )
            }
        }
    }
}

/** One option of a [UnefyChoiceField]: the value sent, and the words shown. */
data class UnefyChoice(val key: String, val label: String)

/** A yes/no, as a row rather than a lone switch floating in the margin. */
@Composable
fun UnefySwitchField(
    label: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
    description: String? = null,
) {
    Column(modifier = modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { onCheckedChange(!checked) }
                .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.sm),
            horizontalArrangement = Arrangement.spacedBy(UnefySpacing.md),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(text = label, style = MaterialTheme.typography.bodyLarge)
                if (description != null) {
                    Text(
                        text = description,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Switch(checked = checked, onCheckedChange = onCheckedChange)
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
    }
}

/**
 * A titled group of fields — the same heading [UnefyDetailSection] uses, so a
 * record's sections keep their names when it becomes editable.
 */
@Composable
fun UnefyFormSection(title: String, content: @Composable ColumnScope.() -> Unit) {
    Text(
        text = title,
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(
            start = UnefySpacing.screen,
            end = UnefySpacing.screen,
            top = UnefySpacing.lg,
            bottom = UnefySpacing.sm,
        ),
    )
    Column(modifier = Modifier.fillMaxWidth(), content = content)
}

/**
 * The bar that appears once something has been changed.
 *
 * This is what replaces a form's permanent save button, and it is the whole
 * reason editing can live on the detail screen: there is no "edit mode" to enter
 * or leave, only a record that either has unsaved changes or does not. Nothing
 * is written until [onSave] — Notion-style save-per-keystroke would put a
 * mistyped surname into the club's records and into the sync queue before the
 * finger left the key.
 *
 * [onDiscard] is not decoration either. Without a way back, an accidental edit
 * on a record somebody only opened to read has no exit but retyping.
 */
@Composable
fun UnefySaveBar(
    visible: Boolean,
    onSave: () -> Unit,
    onDiscard: () -> Unit,
    modifier: Modifier = Modifier,
    saving: Boolean = false,
    saveLabel: String = stringResource(R.string.form_save),
    blockedReason: String? = null,
) {
    AnimatedVisibility(
        visible = visible,
        enter = slideInVertically(UnefyMotion.spatialFast()) { it },
        exit = slideOutVertically(UnefyMotion.spatialFast()) { it },
        modifier = modifier,
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            if (blockedReason != null) {
                Text(
                    text = blockedReason,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(
                        start = UnefySpacing.screen,
                        end = UnefySpacing.screen,
                        top = UnefySpacing.sm,
                    ),
                )
            }
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(UnefySpacing.screen),
                horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                // Text, not outlined: rule 3 of "avoiding flatness" allows one
                // emphasis per screen, and it belongs to saving.
                TextButton(onClick = onDiscard, enabled = !saving) {
                    Text(stringResource(R.string.form_discard))
                }
                Button(
                    onClick = onSave,
                    enabled = blockedReason == null && !saving,
                    modifier = Modifier.weight(1f),
                ) {
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        if (saving) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(SPINNER),
                                strokeWidth = 2.dp,
                                color = MaterialTheme.colorScheme.onPrimary,
                            )
                        }
                        Text(saveLabel)
                    }
                }
            }
        }
    }
}

private val SPINNER = 16.dp

/** Club evenings start in the evening. Saves two taps in the common case. */
private const val DEFAULT_HOUR = 19
