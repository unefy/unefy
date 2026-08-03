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
 * Renders nothing when every field inside it is empty — an empty "Banking"
 * heading over nothing is worse than no heading. Fields register through
 * [UnefyFieldScope.Field], which drops null and blank values, so the caller
 * lists everything it *could* show and the section decides what survives.
 */
@Composable
fun UnefyDetailSection(title: String, content: @Composable UnefyFieldScope.() -> Unit) {
    val scope = UnefyFieldScope()
    scope.content()
    if (scope.fields.isEmpty()) return

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
    scope.fields.forEach { field ->
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

class UnefyFieldScope internal constructor() {
    internal val fields = mutableListOf<UnefyFieldData>()
}

internal data class UnefyFieldData(val label: String, val value: String, val mono: Boolean)

/** Registers a field; null or blank values simply do not appear. */
fun UnefyFieldScope.Field(label: String, value: String?, mono: Boolean = false) {
    if (!value.isNullOrBlank()) fields += UnefyFieldData(label, value, mono)
}

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
