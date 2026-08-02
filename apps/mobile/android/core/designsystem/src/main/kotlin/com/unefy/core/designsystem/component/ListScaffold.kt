package com.unefy.core.designsystem.component

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.unefy.core.designsystem.theme.UnefySpacing
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeEffect
import dev.chrisbanes.haze.hazeSource

/** Search wiring for a screen whose list can be filtered. */
@Immutable
data class ScreenSearch(
    val value: String,
    val onValueChange: (String) -> Unit,
    val placeholder: String,
    val enabled: Boolean = true,
)

/**
 * The scaffold every list screen uses.
 *
 * **Why the header floats.** Material's medium and large app bars are fixed
 * containers of 112dp and 152dp with the title pinned to the bottom edge, which
 * leaves most of that height empty; M3 Expressive no longer recommends them.
 * Modern apps put function up there instead — Gmail and Play show search and the
 * account, not a title. So this header is one row of working controls.
 *
 * It is drawn *over* the list, and the list is padded to start beneath it. That
 * is what makes glass possible at all: a translucent surface needs something
 * behind it. Compose can blur a layer's own content but not the content behind
 * it, so the backdrop comes from Haze — the list is the blur source, the header
 * is the glass.
 *
 * Translucency without blur was never an option: text scrolling under a
 * semi-transparent bar stays legible enough to read as a rendering fault rather
 * than as a material.
 *
 * The scaffold owns the `LazyColumn` so a screen cannot quietly opt out of any
 * of this.
 */
@Composable
fun UnefyListScaffold(
    title: String,
    modifier: Modifier = Modifier,
    subtitle: String? = null,
    search: ScreenSearch? = null,
    /** Leading slot — back belongs on the left on Android, not among the actions. */
    navigationIcon: (@Composable () -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {},
    floatingActionButton: @Composable () -> Unit = {},
    listState: LazyListState = rememberLazyListState(),
    content: LazyListScope.() -> Unit,
) {
    // The shell's state when there is one, so the navigation bar blurs the same
    // list this screen is showing; a local one otherwise, for previews.
    val hazeState = LocalHazeState.current ?: remember { HazeState() }
    val density = LocalDensity.current

    // Measured, not fixed: the header's height depends on the status bar inset
    // and on whether a subtitle is present, and the list must start exactly
    // below it.
    var headerHeight by remember { mutableStateOf(0.dp) }

    Scaffold(
        modifier = modifier,
        floatingActionButton = floatingActionButton,
        contentWindowInsets = WindowInsets.safeDrawing,
    ) { insets ->
        Box(modifier = Modifier.fillMaxSize()) {
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .fillMaxSize()
                    .hazeSource(hazeState),
                contentPadding = PaddingValues(
                    top = headerHeight,
                    // The floating bar overlays the list, so its height is not in
                    // the Scaffold insets — the list has to clear it itself.
                    bottom = insets.calculateBottomPadding() + glassBarClearance,
                ),
                content = content,
            )

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .align(Alignment.TopCenter)
                    .onSizeChanged { headerHeight = with(density) { it.height.toDp() } }
                    .hazeEffect(
                        state = hazeState,
                        // Thin, not thick: the point is to keep a hint of the
                        // list visible underneath, not to hide it.
                        style = unefyGlassStyle(),
                    )
                    .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Top))
                    .padding(
                        start = if (navigationIcon != null) UnefySpacing.xs else UnefySpacing.screen,
                        end = UnefySpacing.screen,
                        top = UnefySpacing.md,
                        bottom = UnefySpacing.sm,
                    ),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
            ) {
                navigationIcon?.invoke()

                if (search != null) {
                    UnefySearchField(
                        value = search.value,
                        onValueChange = search.onValueChange,
                        placeholder = search.placeholder,
                        enabled = search.enabled,
                        modifier = Modifier.weight(1f),
                    )
                } else {
                    HeaderTitle(
                        title = title,
                        subtitle = subtitle,
                        modifier = Modifier.weight(1f),
                    )
                }
                actions()
            }
        }
    }
}

@Composable
private fun HeaderTitle(title: String, subtitle: String?, modifier: Modifier = Modifier) {
    Column(modifier = modifier) {
        Text(
            // headlineSmall, not titleLarge: at 22sp the heading sat a hair
            // above the 16sp row titles below it and read as just another line.
            // 24sp semibold is a step the eye registers as a level.
            text = title,
            style = MaterialTheme.typography.headlineSmall,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        subtitle?.let {
            Text(
                text = it,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}
