package com.unefy.core.designsystem.component

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.unefy.core.designsystem.theme.UnefyNumericTextStyle
import com.unefy.core.designsystem.theme.UnefySpacing

/**
 * A titled block of label/value fields on a detail screen.
 *
 * Renders nothing when every field is empty — an empty "Banking" heading over
 * nothing is worse than no heading. [Field] returns null for a null or blank
 * value, so the caller lists everything it *could* show and the section decides
 * what survives.
 *
 * The fields arrive as values rather than as a composable block, and that is the
 * whole point. This was a `@Composable UnefyFieldScope.() -> Unit` that collected
 * its fields into a plain list while it composed, and then rendered from that
 * list in the same function body. Compose is free to recompose the block on its
 * own — it does exactly that when the record the block closes over changes,
 * because the block's captured values are what it tracks — while skipping this
 * function, whose own arguments still compare equal. The fields were then
 * appended to a list nothing re-read, so the section kept rendering the previous
 * record: a member detail screen showed the newly opened member's name in its
 * header over the previously opened member's address, category and IBAN.
 *
 * A list parameter cannot drift that way. It compares unequal when the data
 * changes, so this function recomposes, and there is no state between the two.
 */
@Composable
fun UnefyDetailSection(title: String, fields: List<UnefyField?>) {
    val visible = fields.filterNotNull()
    if (visible.isEmpty()) return

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
    visible.forEach { field ->
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.sm),
        ) {
            Text(
                text = field.label,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = field.value,
                style = if (field.mono) {
                    UnefyNumericTextStyle
                } else {
                    MaterialTheme.typography.bodyLarge
                },
            )
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
    }
}

/** One label/value row, as data. */
data class UnefyField(val label: String, val value: String, val mono: Boolean = false)

/**
 * A field, or null when there is nothing to show.
 *
 * Capitalised because it reads as a constructor at the call site — the same
 * reason `Color(…)` and `Offset(…)` are. Nullable so that a section can be
 * written as a flat list of everything a record might carry, and the blanks fall
 * out on their own.
 */
fun Field(label: String, value: String?, mono: Boolean = false): UnefyField? =
    if (value.isNullOrBlank()) null else UnefyField(label, value, mono)

/**
 * A small labelled state, as a pill. The caller picks the colour role — status
 * semantics (success, warning, error, neutral) belong to the feature, not here.
 */
@Composable
fun UnefyPill(text: String, container: Color, content: Color) {
    Surface(shape = CircleShape, color = container) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelMedium,
            color = content,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
        )
    }
}
