package com.unefy.core.designsystem.component

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.unefy.core.designsystem.R
import com.unefy.core.designsystem.theme.LocalUnefyColors
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme

/**
 * Says that what is on screen is not current, and why.
 *
 * A banner rather than a snackbar, and the difference is the point. A snackbar
 * reports an event — it appears once and is gone, which suited a screen that
 * fetched on demand and either had fresh data or an error. A screen reading from a
 * local mirror has a third state that neither of those covers: it is showing real
 * data that is simply not current, and it will keep showing it. That is a
 * condition, and a condition needs a surface that stays.
 *
 * Warning tones rather than error: nothing is broken. The list is right, just not
 * necessarily right *now*.
 */
@Composable
fun UnefyStaleBanner(
    visible: Boolean,
    text: String,
    modifier: Modifier = Modifier,
) {
    val extended = LocalUnefyColors.current

    AnimatedVisibility(visible = visible, modifier = modifier) {
        Surface(color = extended.warningContainer, modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.padding(
                    horizontal = UnefySpacing.screen,
                    vertical = UnefySpacing.sm,
                ),
                horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    painter = painterResource(R.drawable.ic_cloud_off),
                    contentDescription = null,
                    tint = extended.onWarningContainer,
                    modifier = Modifier.size(ICON_SIZE),
                )
                Text(
                    text = text,
                    style = MaterialTheme.typography.labelLarge,
                    color = extended.onWarningContainer,
                )
            }
        }
    }
}

private val ICON_SIZE = 18.dp

@Preview
@Composable
private fun StaleBannerPreview() {
    UnefyTheme {
        UnefyStaleBanner(visible = true, text = "Keine Verbindung — Liste ist möglicherweise veraltet")
    }
}
