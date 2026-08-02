package com.unefy.core.designsystem.component

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * The separator between list rows.
 *
 * Inset to where the text starts rather than running under the avatar — a line
 * that cuts through the leading element reads as a table, not a list. Shared so
 * two lists cannot disagree about it, which is exactly what happened before.
 */
@Composable
fun UnefyRowDivider(modifier: Modifier = Modifier, startInset: Dp = RowTextInset) {
    HorizontalDivider(
        color = MaterialTheme.colorScheme.outlineVariant,
        modifier = modifier.padding(start = startInset),
    )
}

/** Screen margin + avatar + gap: where a row's text column begins. */
val RowTextInset: Dp = 72.dp
