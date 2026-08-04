package com.unefy.core.designsystem.component

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import com.unefy.core.designsystem.theme.UnefySpacing

/**
 * The one empty/error state, shared by every screen.
 *
 * A headline, an optional explanation, an optional action — always the same
 * type styles and gaps, so "no events" and "no competitions" cannot drift
 * apart. Callers that live in a `LazyColumn` pass
 * `Modifier.fillParentMaxHeight(UNEFY_STATE_FILL)` so the message centres in
 * the space below the header rather than hugging the top.
 */
@Composable
fun UnefyCenteredState(
    title: String,
    modifier: Modifier = Modifier,
    body: String? = null,
    action: (@Composable () -> Unit)? = null,
) {
    Column(
        modifier = modifier.fillMaxWidth().padding(UnefySpacing.lg),
        verticalArrangement = Arrangement.spacedBy(UnefySpacing.sm, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.headlineSmall,
            textAlign = TextAlign.Center,
        )
        body?.let {
            Text(
                text = it,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
        }
        action?.invoke()
    }
}

/**
 * How much of the viewport a full-screen state fills below the header — the
 * shared value, so the message sits at the same height on every screen.
 */
const val UNEFY_STATE_FILL = 0.7f
