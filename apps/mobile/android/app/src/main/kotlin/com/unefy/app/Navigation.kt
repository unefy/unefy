package com.unefy.app

import androidx.annotation.DrawableRes
import androidx.annotation.StringRes
import androidx.compose.animation.AnimatedContentTransitionScope
import androidx.compose.animation.ContentTransform
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.ShortNavigationBar
import androidx.compose.material3.ShortNavigationBarItem
import androidx.compose.material3.Text
import androidx.compose.material3.adaptive.currentWindowAdaptiveInfo
import androidx.compose.material3.adaptive.navigationsuite.NavigationSuiteScaffoldDefaults
import androidx.compose.material3.adaptive.navigationsuite.NavigationSuiteType
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.key
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.boundsInRoot
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInRoot
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.navigation3.runtime.NavBackStack
import androidx.navigation3.runtime.NavEntry
import androidx.navigation3.runtime.NavKey
import androidx.navigation3.runtime.entryProvider
import androidx.navigation3.runtime.rememberNavBackStack
import androidx.navigation3.scene.Scene
import androidx.navigation3.ui.NavDisplay
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.component.LocalGlassBarHeight
import com.unefy.core.designsystem.component.LocalHazeState
import com.unefy.core.designsystem.component.unefyGlassStyle
import com.unefy.core.designsystem.theme.UnefyMotion
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.unefy.app.nav.MoreRoute
import com.unefy.app.nav.NavDragGhost
import com.unefy.app.nav.NavDragState
import com.unefy.app.nav.LocalNavDragState
import com.unefy.app.nav.NavSettingsViewModel
import com.unefy.app.nav.TopLevel
import com.unefy.app.nav.permittedDestinations
import com.unefy.app.ui.accountActions
import com.unefy.core.model.ClubRole
import com.unefy.feature.attendance.MemberCodeRoute
import com.unefy.feature.attendance.ScannerRoute
import com.unefy.feature.competitions.CompetitionsRoute
import com.unefy.feature.competitions.ScoreboardRoute
import com.unefy.feature.dues.DuesRoute
import com.unefy.feature.dues.MyDuesRoute
import com.unefy.feature.events.EventsRoute
import com.unefy.feature.members.DirectoryRoute
import com.unefy.feature.members.MemberDetailRoute
import com.unefy.feature.members.MyProfileRoute
import com.unefy.feature.members.MembersRoute
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeEffect

/** A fifth of the width — Material's shared axis travels a short distance. */
private const val SLIDE_DIVISOR = 5

/**
 * Material shared-axis motion along X.
 *
 * NavDisplay's default is a plain cross-fade, which is what a web page does and
 * exactly what makes a native app feel like one. Here screens travel: the
 * incoming one enters from the direction of travel, the outgoing one leaves
 * against it, over a short distance so it reads as depth rather than a
 * slideshow. Specs come from UnefyMotion — the same spring as the rest of the
 * app, not a hand-picked duration.
 */
private const val BAR_DRAGGED_ALPHA = 0.3f

private val forward: AnimatedContentTransitionScope<Scene<NavKey>>.() -> ContentTransform = {
    slideInHorizontally(UnefyMotion.spatial()) { width -> width / SLIDE_DIVISOR } +
        fadeIn(UnefyMotion.effects()) togetherWith
        slideOutHorizontally(UnefyMotion.spatial()) { width -> -width / SLIDE_DIVISOR } +
        fadeOut(UnefyMotion.effects())
}

private val backward: AnimatedContentTransitionScope<Scene<NavKey>>.() -> ContentTransform = {
    slideInHorizontally(UnefyMotion.spatial()) { width -> -width / SLIDE_DIVISOR } +
        fadeIn(UnefyMotion.effects()) togetherWith
        slideOutHorizontally(UnefyMotion.spatial()) { width -> width / SLIDE_DIVISOR } +
        fadeOut(UnefyMotion.effects())
}

/**
 * The back stack is plain Compose state — Navigation 3's core idea. Adding a
 * destination is `backStack.add(key)`; there is no graph to keep in sync.
 *
 * The shell adapts: a floating glass bar on phones, a rail beside the content on
 * anything wider. That branch is what keeps the layout legal on the tablets and
 * foldables targetSdk 36 forces us to support.
 */
@Composable
fun MainNavigation(
    clubName: String?,
    accountEmail: String?,
    accountName: String?,
    role: ClubRole,
    onSignOut: () -> Unit,
) {
    val accountActions = accountActions(
        email = accountEmail,
        displayName = accountName,
        onSignOut = onSignOut,
    )

    // The person's own arrangement, not one we guessed. Empty until DataStore
    // answers, so the bar renders nothing rather than flashing a default order
    // that is about to be replaced.
    val settings: NavSettingsViewModel = hiltViewModel()
    settings.setRole(role)
    val destinations by settings.visible.collectAsStateWithLifecycle()

    val start = destinations.firstOrNull() ?: permittedDestinations(role).first()
    val backStack = rememberNavBackStack(start.key)
    var selected: TopLevel? by rememberSaveable(role) { mutableStateOf(null) }

    var onMoreTab by rememberSaveable(role) { mutableStateOf(false) }

    val select: (TopLevel) -> Unit = { destination ->
        selected = destination
        onMoreTab = false
        // Switching sections resets the stack rather than piling sections on top
        // of each other — back from a section root leaves the app, as Android
        // expects.
        backStack.clear()
        backStack.add(destination.key)
    }

    val selectMore: () -> Unit = {
        onMoreTab = true
        backStack.clear()
        backStack.add(MoreKey)
    }

    // Hand-rolled instead of NavigationSuiteScaffold, for one reason: that
    // component lays the content out *beside* the navigation, so nothing is ever
    // behind the bar. Glass needs a backdrop. The adaptive decision it made for
    // us is a single branch, so owning it costs little — and the bar stays the
    // compact Expressive one rather than the 80dp default.
    val hazeState = remember { HazeState() }
    val dragState = remember { NavDragState() }
    val density = LocalDensity.current
    var barHeight by remember { mutableStateOf(0.dp) }

    // Every bar variant, not just one. Comparing against NavigationBar alone
    // silently selected the rail on phones, because this version returns
    // ShortNavigationBarCompact for a compact window — and the previous code
    // only ever *swapped* that value, so the mismatch stayed invisible.
    val suiteType = NavigationSuiteScaffoldDefaults.navigationSuiteType(currentWindowAdaptiveInfo())
    val onBottomBar = suiteType == NavigationSuiteType.NavigationBar ||
        suiteType == NavigationSuiteType.ShortNavigationBarCompact ||
        suiteType == NavigationSuiteType.ShortNavigationBarMedium

    // SideEffect, not a bare assignment: writing snapshot state while composing
    // is what makes Compose complain about a value read after being written.
    SideEffect { dragState.barSlots = destinations.size + 1 }

    CompositionLocalProvider(
        LocalHazeState provides hazeState,
        LocalNavDragState provides dragState,
        // A rail sits beside the content, so nothing has to clear it.
        LocalGlassBarHeight provides if (onBottomBar) barHeight else 0.dp,
    ) {
        if (onBottomBar) {
            Box(modifier = Modifier.fillMaxSize()) {
                NavHost(backStack, clubName, role, accountActions)

                ShortNavigationBar(
                    modifier = Modifier
                        .align(Alignment.BottomCenter)
                        .onSizeChanged { barHeight = with(density) { it.height.toDp() } }
                        // Root coordinates: the grid lives in another subtree and
                        // this is the only frame both sides share.
                        .onGloballyPositioned { dragState.barBounds = it.boundsInRoot() }
                        .hazeEffect(state = hazeState, style = unefyGlassStyle()),
                    // Transparent: the glass underneath is the surface now.
                    containerColor = Color.Transparent,
                ) {
                    val dropTarget = dragState.dropIndexOrNull()
                    destinations.forEachIndexed { index, destination ->
                        // key(): each item keeps its own remembered origin even
                        // when the arrangement is reordered mid-drag.
                        key(destination) {
                        var origin by remember { mutableStateOf(Offset.Zero) }
                        ShortNavigationBarItem(
                            // The bar is a drag source too, now that the grid
                            // only shows what is not already here — otherwise
                            // there would be no way to reorder or take out.
                            modifier = Modifier
                                .alpha(if (dragState.dragged == destination) BAR_DRAGGED_ALPHA else 1f)
                                .onGloballyPositioned { origin = it.positionInRoot() }
                                .pointerInput(destination) {
                                    detectDragGesturesAfterLongPress(
                                        onDragStart = { local ->
                                            dragState.begin(destination, origin + local)
                                        },
                                        onDrag = { _, amount -> dragState.moveBy(amount) },
                                        onDragEnd = {
                                            val target = dragState.dropIndexOrNull()
                                            dragState.cancel()
                                            if (target != null) {
                                                settings.placeAt(destination, target)
                                            } else {
                                                // Dragged out of the bar: back on
                                                // the shelf under "more".
                                                settings.remove(destination)
                                            }
                                        },
                                        onDragCancel = { dragState.cancel() },
                                    )
                                },
                            // While dragging, the slot under the finger shows as
                            // selected — without it you are dropping blind.
                            selected = if (dropTarget != null) {
                                index == dropTarget
                            } else {
                                destination == selected && !onMoreTab
                            },
                            onClick = { select(destination) },
                            icon = {
                                Icon(
                                    painter = painterResource(destination.icon),
                                    contentDescription = null,
                                )
                            },
                            label = { Text(stringResource(destination.label)) },
                        )
                        }
                    }

                    // Fixed fifth slot: it is where anything not in the bar lives,
                    // and where the bar itself is rearranged.
                    ShortNavigationBarItem(
                        selected = onMoreTab,
                        onClick = selectMore,
                        icon = {
                            Icon(
                                painter = painterResource(DesignR.drawable.ic_more_horiz),
                                contentDescription = null,
                            )
                        },
                        label = { Text(stringResource(R.string.nav_more)) },
                    )
                }

                // Above the bar and the content both, so it is never clipped by
                // whatever it is being dragged over.
                dragState.dragged?.let { dragged ->
                    Box(
                        modifier = Modifier.graphicsLayer {
                            translationX = dragState.position.x - size.width / 2f
                            translationY = dragState.position.y - size.height / 2f
                        },
                    ) {
                        NavDragGhost(dragged)
                    }
                }
            }
        } else {
            Row(modifier = Modifier.fillMaxSize()) {
                NavigationRail {
                    destinations.forEach { destination ->
                        NavigationRailItem(
                            selected = destination == selected && !onMoreTab,
                            onClick = { select(destination) },
                            icon = {
                                Icon(
                                    painter = painterResource(destination.icon),
                                    contentDescription = null,
                                )
                            },
                            label = { Text(stringResource(destination.label)) },
                        )
                    }
                    NavigationRailItem(
                        selected = onMoreTab,
                        onClick = selectMore,
                        icon = {
                            Icon(
                                painter = painterResource(DesignR.drawable.ic_more_horiz),
                                contentDescription = null,
                            )
                        },
                        label = { Text(stringResource(R.string.nav_more)) },
                    )
                }
                Box(modifier = Modifier.weight(1f)) {
                    NavHost(backStack, clubName, role, accountActions)
                }
            }
        }
    }
}

/** The destination graph, identical on phone and on wide windows. */
@Composable
private fun NavHost(
    backStack: NavBackStack<NavKey>,
    clubName: String?,
    role: ClubRole,
    accountActions: @Composable RowScope.() -> Unit,
) {
    NavDisplay(
        backStack = backStack,
        onBack = { backStack.removeLastOrNull() },
        transitionSpec = forward,
        popTransitionSpec = backward,
        // Same motion, but scrubbed by the predictive-back gesture instead
        // of played: it follows the finger and reverses if released.
        predictivePopTransitionSpec = { backward() },
        entryProvider = unefyEntryProvider(
            clubName = clubName,
            role = role,
            accountActions = accountActions,
            onOpen = { key -> backStack.add(key) },
            onSwitchSection = { key ->
                backStack.clear()
                backStack.add(key)
            },
            onBack = { backStack.removeLastOrNull() },
        ),
    )
}

/**
 * Key → screen, as a plain function of callbacks rather than of the back stack.
 *
 * Split out of [NavHost] for one reason: a missing `entry<>` is invisible to the
 * compiler and only surfaces as a crash when someone taps that section — which
 * is exactly how the Wettkämpfe tab once shipped broken. Without the back stack
 * in the signature this is callable from a plain JVM test, so
 * `EntryProviderCoverageTest` can ask for every [UnefyNavKey] and fail the build
 * instead of the device.
 */
internal fun unefyEntryProvider(
    clubName: String?,
    role: ClubRole,
    accountActions: @Composable RowScope.() -> Unit,
    onOpen: (NavKey) -> Unit,
    onSwitchSection: (NavKey) -> Unit,
    onBack: () -> Unit,
): (NavKey) -> NavEntry<NavKey> = entryProvider {
    entry<MembersKey> {
        MembersRoute(
            clubName = clubName,
            actions = accountActions,
            onMemberClick = { id -> onOpen(MemberDetailKey(id)) },
        )
    }
    entry<MemberDetailKey> { key ->
        MemberDetailRoute(memberId = key.memberId, onBack = onBack)
    }
    entry<EventsKey> { EventsRoute(actions = accountActions) }
    entry<DuesKey> { DuesRoute(actions = accountActions) }
    entry<ProfileKey> { MyProfileRoute(actions = accountActions) }
    entry<DirectoryKey> { DirectoryRoute(actions = accountActions) }
    entry<MyDuesKey> { MyDuesRoute(actions = accountActions) }
    entry<AttendanceCodeKey> { MemberCodeRoute(actions = accountActions) }
    entry<ScannerKey> { ScannerRoute(actions = accountActions) }
    entry<CompetitionsKey> {
        CompetitionsRoute(
            actions = accountActions,
            onCompetitionClick = { id, name -> onOpen(ScoreboardKey(id, name)) },
        )
    }
    entry<MoreKey> {
        MoreRoute(
            role = role,
            actions = accountActions,
            // Tapping a section in "more" goes there without adding it to the
            // bar; adding is the explicit gesture below.
            onDestinationClick = { destination -> onSwitchSection(destination.key) },
        )
    }
    entry<ScoreboardKey> { key ->
        ScoreboardRoute(
            competitionId = key.competitionId,
            competitionName = key.competitionName,
            onBack = onBack,
        )
    }
}
