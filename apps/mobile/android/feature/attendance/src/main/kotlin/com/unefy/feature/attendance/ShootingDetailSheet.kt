package com.unefy.feature.attendance

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuAnchorType
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import com.unefy.core.designsystem.theme.UnefySpacing

/**
 * What somebody shot, entered at the range table.
 *
 * A sheet for the same reason the manual pick is one: the supervisor is standing
 * at the table with the list open, and a separate destination would make "Erika
 * shot forty rounds of air rifle" cost a round trip through navigation.
 *
 * Three fields, all optional. An evening where only the round count is known is
 * still worth recording, and forcing a discipline would produce a wrong one.
 *
 * State lives here rather than in the view model: it is a form being typed, and
 * the answer that matters is the one that comes back from the server. `remember`
 * is keyed on the row so opening a second person's sheet does not inherit the
 * first person's entries.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun ShootingDetailSheet(
    entry: CheckedInEntry,
    detail: ShootingDetail?,
    disciplines: List<ClubDiscipline>,
    saving: Boolean,
    onSave: (clubDisciplineId: String?, weaponCategory: String?, roundsFired: Int?) -> Unit,
    onDismiss: () -> Unit,
) {
    var discipline by remember(entry.key) { mutableStateOf(detail?.clubDisciplineId) }
    var weapon by remember(entry.key) { mutableStateOf(detail?.weaponCategory) }
    var rounds by remember(entry.key) {
        mutableStateOf(detail?.roundsFired?.toString().orEmpty())
    }
    var disciplinesExpanded by remember { mutableStateOf(false) }

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
                text = entry.memberName.ifBlank {
                    stringResource(R.string.scanner_unknown_member)
                },
                style = MaterialTheme.typography.titleMedium,
            )
            Text(
                text = stringResource(R.string.shooting_sheet_hint),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            ExposedDropdownMenuBox(
                expanded = disciplinesExpanded,
                onExpandedChange = { disciplinesExpanded = it },
            ) {
                OutlinedTextField(
                    value = disciplines.firstOrNull { it.id == discipline }?.name
                        ?: stringResource(R.string.shooting_none),
                    onValueChange = {},
                    readOnly = true,
                    label = { Text(stringResource(R.string.shooting_discipline)) },
                    trailingIcon = {
                        ExposedDropdownMenuDefaults.TrailingIcon(expanded = disciplinesExpanded)
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .menuAnchor(ExposedDropdownMenuAnchorType.PrimaryNotEditable),
                )
                ExposedDropdownMenu(
                    expanded = disciplinesExpanded,
                    onDismissRequest = { disciplinesExpanded = false },
                ) {
                    // "Nothing chosen" is an option, not the absence of one: a
                    // discipline entered by mistake has to be clearable.
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.shooting_none)) },
                        onClick = {
                            discipline = null
                            disciplinesExpanded = false
                        },
                    )
                    disciplines.forEach { option ->
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
            // Segmented rather than a second dropdown: three fixed options that
            // fit on one line, and one tap instead of two.
            SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
                WEAPON_CATEGORIES.forEachIndexed { index, category ->
                    SegmentedButton(
                        selected = weapon == category,
                        // Tapping the selected one clears it — the only way back
                        // to "not specified" without leaving the sheet.
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

            Button(
                onClick = {
                    onSave(discipline, weapon, rounds.takeIf { it.isNotBlank() }?.toIntOrNull())
                },
                enabled = !saving,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    stringResource(
                        if (saving) R.string.shooting_saving else R.string.shooting_save,
                    ),
                )
            }
        }
    }
}

/**
 * The German label for a weapon category.
 *
 * An unknown value is shown as it arrived rather than dropped: the server's
 * taxonomy holds `venue_scan` and `nfc_tap` beyond what this version knows, and a
 * blank chip would hide a value somebody entered.
 */
@Composable
internal fun weaponLabel(category: String): String = when (category) {
    "kurzwaffe" -> stringResource(R.string.shooting_weapon_kurzwaffe)
    "langwaffe" -> stringResource(R.string.shooting_weapon_langwaffe)
    "luftdruck" -> stringResource(R.string.shooting_weapon_luftdruck)
    else -> category
}
