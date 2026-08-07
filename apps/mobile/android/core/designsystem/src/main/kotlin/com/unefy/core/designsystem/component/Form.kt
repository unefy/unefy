package com.unefy.core.designsystem.component

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuAnchorType
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.text.KeyboardOptions
import com.unefy.core.designsystem.R
import com.unefy.core.designsystem.theme.UnefySpacing
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle

/**
 * The form building blocks.
 *
 * Material's `OutlinedTextField` rather than something hand-rolled: a form is
 * the one place where the platform's own affordances — the floating label, the
 * error colour, the IME action, the accessibility tree — are worth more than a
 * consistent silhouette. The theme already makes them look like the rest of the
 * app, because the colour scheme they read is ours.
 *
 * What is *not* Material's: [UnefyFormActions] and the validation vocabulary.
 * Every form in this app saves the same way — into the local queue, never
 * straight to the server — so the button says the same thing in every one of
 * them, and its disabled reason is a string the caller supplies rather than a
 * silently dead control.
 */

/** A labelled line of text. */
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
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = modifier.fillMaxWidth(),
        // The asterisk rather than a separate "required" adornment: it is the
        // convention every form on the web app already uses, and a second
        // vocabulary for the same idea is worse than a plain one.
        label = { Text(if (required) "$label *" else label) },
        isError = error != null,
        supportingText = error?.let { { Text(it) } },
        singleLine = singleLine,
        minLines = if (singleLine) 1 else 3,
        keyboardOptions = KeyboardOptions(keyboardType = keyboardType, imeAction = imeAction),
    )
}

/**
 * A date, picked rather than typed.
 *
 * [value] and [onValueChange] speak ISO-8601 (`2026-08-08`), which is what the
 * API wants and what sorts correctly; the field shows it in the device's
 * format. Typing is deliberately not offered — a birthday entered as `08.03.`
 * in a German club and read as March 8th somewhere else is the kind of bug that
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
    val shown = parsed?.format(DateTimeFormatter.ofLocalizedDate(FormatStyle.MEDIUM)).orEmpty()

    OutlinedTextField(
        value = shown,
        onValueChange = {},
        modifier = modifier.fillMaxWidth(),
        label = { Text(if (required) "$label *" else label) },
        readOnly = true,
        isError = error != null,
        supportingText = error?.let { { Text(it) } },
        singleLine = true,
        trailingIcon = {
            TextButton(onClick = { picking = true }) {
                Text(stringResource(R.string.form_pick_date))
            }
        },
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

/** One choice out of a short, fixed list. */
@OptIn(ExperimentalMaterial3Api::class)
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

    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = it },
        modifier = modifier.fillMaxWidth(),
    ) {
        OutlinedTextField(
            value = selected?.label.orEmpty(),
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier
                .menuAnchor(ExposedDropdownMenuAnchorType.PrimaryNotEditable)
                .fillMaxWidth(),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
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

/** A titled group of fields. [UnefyDetailSection]'s counterpart for input. */
@Composable
fun UnefyFormSection(title: String, content: @Composable ColumnScope.() -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.sm),
        verticalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        content()
    }
}

/**
 * The save row that closes every form.
 *
 * [saveLabel] is the caller's because "Anlegen" and "Speichern" are different
 * promises. [blockedReason] is shown when the button is disabled — a control
 * that does nothing and says nothing about why is the single most common way a
 * form wastes somebody's afternoon.
 */
@Composable
fun UnefyFormActions(
    saveLabel: String,
    onSave: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    saving: Boolean = false,
    blockedReason: String? = null,
    error: String? = null,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.md),
        verticalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
    ) {
        if (error != null) {
            Text(
                text = error,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.error,
            )
        } else if (!enabled && blockedReason != null) {
            Text(
                text = blockedReason,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        Button(
            onClick = onSave,
            enabled = enabled && !saving,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (saving) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary,
                    )
                }
                Text(saveLabel)
            }
        }
    }
}
