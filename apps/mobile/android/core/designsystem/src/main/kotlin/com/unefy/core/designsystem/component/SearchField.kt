package com.unefy.core.designsystem.component

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.input.TextFieldLineLimits
import androidx.compose.foundation.text.input.TextFieldState
import androidx.compose.foundation.text.input.clearText
import androidx.compose.foundation.text.input.rememberTextFieldState
import androidx.compose.material3.Icon
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import com.unefy.core.designsystem.R
import kotlinx.coroutines.flow.drop

/**
 * The field's own text, forwarded to [onValueChange] as it changes.
 *
 * Use this wherever the text also drives something else — a filter, a query, an
 * enabled flag. The state is the field's, and the collaborator is told about
 * changes; what the collaborator does with them never comes back into the field.
 * Reset the text with `state.clearText()`, not by pushing a value in.
 */
@Composable
fun rememberSearchFieldState(onValueChange: (String) -> Unit): TextFieldState {
    val state = rememberTextFieldState()
    // Late-bound so a caller passing a fresh lambda each recomposition does not
    // restart the collector and re-announce the current text.
    val notify by rememberUpdatedState(onValueChange)
    LaunchedEffect(state) {
        snapshotFlow { state.text.toString() }
            // The first emission is the text as it already is, which the caller
            // does not need to be told about.
            .drop(1)
            .collect(notify)
    }
    return state
}

/**
 * A compact search pill.
 *
 * Material's `TextField` is 56dp tall and built for forms — as a search box it
 * dominates the screen it sits on, and the label machinery is dead weight when
 * there is only a placeholder. This is a `BasicTextField` in a pill: 44dp, the
 * same visual weight as a chip row, which is what search should have.
 *
 * **Takes a [TextFieldState], never a `value` + `onValueChange` pair.** As a
 * controlled field it scrambled what people typed: every keystroke travelled to
 * a view model, through `flatMapLatest` and a Room query, and only came back a
 * frame or more later. Until it did, the field was re-rendered with the *old*
 * text, which reset the cursor to position 0 — so the next character was
 * inserted at the front and "beck" arrived as "eckb". A field that owns its own
 * text and cursor cannot be overtaken by its own echo; the query it drives is
 * free to lag behind, because nothing flows back.
 */
@Composable
fun UnefySearchField(
    state: TextFieldState,
    placeholder: String,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    Surface(
        modifier = modifier.fillMaxWidth().height(FIELD_HEIGHT),
        shape = CircleShape,
        color = MaterialTheme.colorScheme.surfaceContainerHigh,
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Icon(
                painter = painterResource(R.drawable.ic_search),
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(ICON_SIZE),
            )

            Box(modifier = Modifier.weight(1f), contentAlignment = Alignment.CenterStart) {
                if (state.text.isEmpty()) {
                    Text(
                        text = placeholder,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                BasicTextField(
                    state = state,
                    enabled = enabled,
                    lineLimits = TextFieldLineLimits.SingleLine,
                    textStyle = LocalTextStyle.current.merge(
                        MaterialTheme.typography.bodyMedium,
                    ).copy(color = MaterialTheme.colorScheme.onSurface),
                    cursorBrush = SolidColor(MaterialTheme.colorScheme.onSurface),
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            if (state.text.isNotEmpty()) {
                // 32dp rather than the icon's 18: a tap target has to be
                // reachable, and the ripple is clipped to the circle so it does
                // not bleed across the pill.
                Box(
                    modifier = Modifier
                        .size(CLEAR_TARGET)
                        .clip(CircleShape)
                        .clickable { state.clearText() },
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        painter = painterResource(R.drawable.ic_close),
                        contentDescription = stringResource(R.string.search_clear),
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.size(ICON_SIZE),
                    )
                }
            }
        }
    }
}
private val FIELD_HEIGHT = 44.dp
private val ICON_SIZE = 18.dp
private val CLEAR_TARGET = 32.dp
