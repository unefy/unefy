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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshDefaults
import androidx.compose.material3.pulltorefresh.pullToRefresh
import androidx.compose.material3.pulltorefresh.rememberPullToRefreshState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
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
 * This header is working rows instead: a title row that is identical on every
 * screen — title, subtitle, account action — and, where a screen searches, the
 * search pill as a second row beneath it. Search never replaces the title;
 * a screen that looks different from its neighbours reads as a different app.
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
 *
 * **Why pull-to-refresh lives here.** Every list in this app is a snapshot taken
 * when its ViewModel was created; nothing pushes updates. Without a refresh
 * gesture the only way to see what someone else just entered in the web app is
 * to leave the section and come back. Screens with three rows made that obvious
 * — a list too short to scroll had no way to be moved at all.
 *
 * @param onRefresh null on screens with nothing to fetch — the "more" screen
 *   reads local preferences, and the scanner is not a list. Passing null
 *   disables the gesture rather than accepting a no-op.
 * @param onLoadMore called once the list is scrolled within
 *   [LOAD_MORE_LOOKAHEAD] rows of its end. Null on screens that fetch
 *   everything in one call. Callers must tolerate being asked again while a
 *   page is already in flight — this fires on scroll position, and knows
 *   nothing about what the ViewModel is doing.
 */
@OptIn(ExperimentalMaterial3Api::class)
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
    isRefreshing: Boolean = false,
    onRefresh: (() -> Unit)? = null,
    onLoadMore: (() -> Unit)? = null,
    /** Shown once as a snackbar, then handed back via [onMessageShown]. */
    message: String? = null,
    onMessageShown: () -> Unit = {},
    /**
     * Drawn under the controls, inside the header — so it stays put while the list
     * scrolls, and the list's top padding accounts for it appearing and going.
     *
     * For standing conditions rather than events: "this list is not current" is
     * true until the next sync succeeds, which is not something a snackbar can
     * express. See [UnefyStaleBanner].
     */
    banner: @Composable () -> Unit = {},
    content: LazyListScope.() -> Unit,
) {
    // Two blur scopes on purpose. The header blurs through a state local to
    // this screen: during a navigation transition two screens are haze
    // sources at once, and a header on the shared state samples the *other*
    // screen too — Check-in's white QR flashed through as a light band. The
    // shell's state still gets the list as a source, so the floating
    // navigation bar (which overlays whichever screens are animating) keeps
    // its frost.
    val headerHaze = remember { HazeState() }
    val shellHaze = LocalHazeState.current
    val density = LocalDensity.current

    // Measured, not fixed: the header's height depends on the status bar inset
    // and on whether a subtitle is present, and the list must start exactly
    // below it.
    var headerHeight by remember { mutableStateOf(0.dp) }

    val pullState = rememberPullToRefreshState()
    val snackbarHostState = remember { SnackbarHostState() }

    // rememberUpdatedState: showSnackbar suspends for the whole duration the
    // snackbar is visible, and the callback that runs afterwards must be the
    // current one, not the one captured when the message arrived.
    val messageShown by rememberUpdatedState(onMessageShown)
    LaunchedEffect(message) {
        if (message != null) {
            snackbarHostState.showSnackbar(message)
            messageShown()
        }
    }

    if (onLoadMore != null) {
        val loadMore by rememberUpdatedState(onLoadMore)
        // derivedStateOf, not a bare read: layoutInfo changes on every scrolled
        // pixel, and without it this would recompose the whole screen the whole
        // way down the list.
        val atEnd by remember(listState) {
            derivedStateOf {
                val info = listState.layoutInfo
                val last = info.visibleItemsInfo.lastOrNull()?.index
                // An empty list is not "at the end" — it has not loaded yet, and
                // asking for page two before page one lands would skip a page.
                last != null && last >= info.totalItemsCount - LOAD_MORE_LOOKAHEAD
            }
        }
        LaunchedEffect(atEnd) { if (atEnd) loadMore() }
    }

    Scaffold(
        modifier = modifier,
        floatingActionButton = floatingActionButton,
        contentWindowInsets = WindowInsets.safeDrawing,
        snackbarHost = {
            // The floating bar overlays the content, so it is not in the
            // Scaffold insets — without this the snackbar hides behind it.
            SnackbarHost(snackbarHostState, modifier = Modifier.padding(bottom = glassBarClearance))
        },
    ) { insets ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                // On the Box rather than the list: this is a nested-scroll
                // connection, and it must see the drag the list leaves
                // unconsumed — which, on a list shorter than the window, is all
                // of it. That is what makes a three-row list pullable at all.
                .pullToRefresh(
                    isRefreshing = isRefreshing,
                    state = pullState,
                    enabled = onRefresh != null,
                    onRefresh = { onRefresh?.invoke() },
                ),
        ) {
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .fillMaxSize()
                    .hazeSource(headerHaze)
                    .then(
                        if (shellHaze != null) Modifier.hazeSource(shellHaze) else Modifier,
                    ),
                contentPadding = PaddingValues(
                    top = headerHeight,
                    // The floating bar overlays the list, so its height is not in
                    // the Scaffold insets — the list has to clear it itself.
                    bottom = insets.calculateBottomPadding() + glassBarClearance,
                ),
                content = content,
            )

            // Before the header and inset by its height, so it emerges from
            // underneath it. Parked above the fold it would sit behind the
            // status bar instead, where the glass cannot hide it.
            if (onRefresh != null) {
                PullToRefreshDefaults.Indicator(
                    state = pullState,
                    isRefreshing = isRefreshing,
                    modifier = Modifier
                        .align(Alignment.TopCenter)
                        .padding(top = headerHeight),
                )
            }

            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .align(Alignment.TopCenter)
                    // On the whole header, banner included, so the list's top
                    // padding follows it. A banner measured outside this would
                    // either cover the first row or leave a gap when it goes.
                    .onSizeChanged { headerHeight = with(density) { it.height.toDp() } }
                    .hazeEffect(
                        state = headerHaze,
                        // Thin, not thick: the point is to keep a hint of the
                        // list visible underneath, not to hide it.
                        style = unefyGlassStyle(),
                    )
                    .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Top)),
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(
                            start = if (navigationIcon != null) {
                                UnefySpacing.xs
                            } else {
                                UnefySpacing.screen
                            },
                            end = UnefySpacing.screen,
                            top = UnefySpacing.md,
                            bottom = UnefySpacing.sm,
                        ),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
                ) {
                    navigationIcon?.invoke()

                    // The title row is identical on every screen — search never
                    // replaces it. A screen that looks different from its
                    // neighbours reads as a different app.
                    HeaderTitle(
                        title = title,
                        subtitle = subtitle,
                        modifier = Modifier.weight(1f),
                    )
                    actions()
                }

                if (search != null) {
                    UnefySearchField(
                        value = search.value,
                        onValueChange = search.onValueChange,
                        placeholder = search.placeholder,
                        enabled = search.enabled,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(
                                start = UnefySpacing.screen,
                                end = UnefySpacing.screen,
                                bottom = UnefySpacing.sm,
                            ),
                    )
                }

                banner()
            }
        }
    }
}

/**
 * The last row while the next page is on its way.
 *
 * A spinner, and deliberately so — the skeleton rule is about a screen that has
 * nothing yet, where a placeholder shaped like the content tells you what is
 * coming. Here the content is already above it and the only question is whether
 * more is on the way. A skeleton row here would read as a member that failed to
 * render.
 */
@Composable
fun UnefyLoadMoreFooter(modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = UnefySpacing.md),
        contentAlignment = Alignment.Center,
    ) {
        CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(20.dp))
    }
}

/** How many rows from the end the next page is asked for. */
private const val LOAD_MORE_LOOKAHEAD = 5

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
