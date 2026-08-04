package com.unefy.core.designsystem.component

import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.unefy.core.designsystem.R
import com.unefy.core.designsystem.theme.UnefyMotion
import com.unefy.core.designsystem.theme.UnefySpacing
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeEffect
import dev.chrisbanes.haze.hazeSource

/**
 * The scaffold for a detail screen, [UnefyListScaffold]'s sibling.
 *
 * The header is a fixed glass bar — the back button never leaves, matching the
 * list screens' glass header — and once the content's own title has scrolled
 * out, [collapsedTitle] fades in next to the arrow so the screen keeps its
 * name. The content is registered as the haze source, which is also what keeps
 * the floating navigation bar frosted rather than transparent over details.
 */
@Composable
fun UnefyDetailScaffold(
    /** Fades in beside the arrow once the header scrolls away; null hides it. */
    collapsedTitle: String?,
    modifier: Modifier = Modifier,
    onBack: (() -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {},
    /** Overlay slot on the whole screen — a snackbar host, typically. */
    overlay: @Composable BoxScope.() -> Unit = {},
    content: @Composable ColumnScope.() -> Unit,
) {
    // The shell's state when there is one, so the navigation bar blurs this
    // screen's content; a local one otherwise, for previews.
    val hazeState = LocalHazeState.current ?: remember { HazeState() }
    val density = LocalDensity.current
    val scrollState = rememberScrollState()

    // Measured, not fixed: the header's height depends on the status bar
    // inset, and the content must start exactly below it.
    var headerHeight by remember { mutableStateOf(0.dp) }

    val titleThresholdPx = with(density) { TITLE_SCROLL_THRESHOLD.toPx() }
    val showCollapsedTitle by remember(titleThresholdPx) {
        // derivedStateOf: the bar recomposes when the threshold is crossed,
        // not on every scrolled pixel.
        derivedStateOf { scrollState.value > titleThresholdPx }
    }

    // Surface, not a bare Box: it provides the background and, crucially, a
    // content color — without it every Text that trusts LocalContentColor
    // renders in the default black on a dark screen.
    Surface(modifier = modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Box(modifier = Modifier.fillMaxSize()) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .hazeSource(hazeState)
                    .verticalScroll(scrollState),
            ) {
                // The glass header overlays the content, so the content clears it
                // itself — same deal as the list's contentPadding.
                Spacer(modifier = Modifier.height(headerHeight))
                content()
                // And the floating navigation bar at the other end.
                Spacer(
                    modifier = Modifier.height(
                        WindowInsets.safeDrawing
                            .only(WindowInsetsSides.Bottom)
                            .asPaddingValues()
                            .calculateBottomPadding() +
                            LocalGlassBarHeight.current + UnefySpacing.lg,
                    ),
                )
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .align(Alignment.TopCenter)
                    .onSizeChanged { headerHeight = with(density) { it.height.toDp() } }
                    .hazeEffect(state = hazeState, style = unefyGlassStyle())
                    .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Top)),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (onBack != null) {
                    IconButton(onClick = onBack) {
                        Icon(
                            painter = painterResource(R.drawable.ic_arrow_back),
                            contentDescription = stringResource(R.string.detail_back),
                        )
                    }
                } else {
                    Spacer(modifier = Modifier.width(UnefySpacing.screen))
                }

                Box(
                    modifier = Modifier
                        .weight(1f)
                        .height(BAR_HEIGHT),
                    contentAlignment = Alignment.CenterStart,
                ) {
                    // Fully qualified: inside the header Row the RowScope
                    // overload shadows the top-level one, and this Box is no
                    // RowScope.
                    androidx.compose.animation.AnimatedVisibility(
                        visible = collapsedTitle != null && showCollapsedTitle,
                        enter = fadeIn(UnefyMotion.effects()),
                        exit = fadeOut(UnefyMotion.effects()),
                    ) {
                        Text(
                            text = collapsedTitle.orEmpty(),
                            style = MaterialTheme.typography.titleMedium,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }

                actions()
            }


            overlay()
        }
    }
}

private val BAR_HEIGHT = 48.dp

/**
 * Roughly where the header's own title line ends. Past this the big title is
 * gone and the bar takes over the name; before it the two would double up.
 */
private val TITLE_SCROLL_THRESHOLD = 64.dp
