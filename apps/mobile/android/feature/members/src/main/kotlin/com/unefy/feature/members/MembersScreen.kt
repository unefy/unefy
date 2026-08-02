package com.unefy.feature.members

import androidx.compose.animation.animateColor
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.component.ScreenSearch
import com.unefy.core.designsystem.component.UnefyListScaffold
import com.unefy.core.designsystem.component.UnefyLoadMoreFooter
import com.unefy.core.designsystem.component.UnefyRowDivider
import com.unefy.core.designsystem.theme.LocalUnefyColors
import com.unefy.core.designsystem.theme.UnefyMotion
import com.unefy.core.designsystem.theme.UnefyNumericTextStyle
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.Member
import com.unefy.core.model.MemberStatus
import com.unefy.core.network.ApiError

@Composable
fun MembersRoute(
    clubName: String?,
    onMemberClick: (String) -> Unit,
    actions: @Composable RowScope.() -> Unit = {},
    viewModel: MembersViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    MembersScreen(
        state = state,
        clubName = clubName,
        actions = actions,
        onMemberClick = onMemberClick,
        onQueryChange = viewModel::onQueryChange,
        onRetry = viewModel::retry,
        onRefresh = viewModel::refresh,
        onLoadMore = viewModel::loadMore,
        onMessageShown = viewModel::onMessageShown,
    )
}

@Composable
fun MembersScreen(
    state: MembersUiState,
    clubName: String? = null,
    onMemberClick: (String) -> Unit = {},
    onQueryChange: (String) -> Unit = {},
    onRetry: () -> Unit = {},
    onRefresh: () -> Unit = {},
    onLoadMore: () -> Unit = {},
    onMessageShown: () -> Unit = {},
    actions: @Composable RowScope.() -> Unit = {},
    modifier: Modifier = Modifier,
) {
    val content = state as? MembersUiState.Content

    UnefyListScaffold(
        title = stringResource(R.string.members_title),
        subtitle = clubName,
        modifier = modifier,
        search = ScreenSearch(
            value = content?.query.orEmpty(),
            onValueChange = onQueryChange,
            placeholder = stringResource(R.string.members_search),
            enabled = state !is MembersUiState.Failure,
        ),
        actions = actions,
        isRefreshing = content?.isRefreshing == true,
        onRefresh = onRefresh,
        onLoadMore = onLoadMore,
        message = stringResource(DesignR.string.refresh_failed)
            .takeIf { content?.refreshFailed == true },
        onMessageShown = onMessageShown,
        floatingActionButton = {
            // The single filled emphasis on this screen.
            FloatingActionButton(onClick = {}) {
                Icon(
                    painter = painterResource(DesignR.drawable.ic_add),
                    contentDescription = stringResource(R.string.members_add),
                )
            }
        },
    ) {
        when (state) {
            MembersUiState.Loading -> membersSkeleton()

            is MembersUiState.Failure -> item {
                ErrorState(state.error, onRetry, Modifier.fillParentMaxHeight(FILL_BELOW_HEADING))
            }

            is MembersUiState.Content -> if (state.members.isEmpty()) {
                item {
                    EmptyState(
                        hasQuery = state.query.isNotBlank(),
                        modifier = Modifier.fillParentMaxHeight(FILL_BELOW_HEADING),
                    )
                }
            } else {
                item(key = "count") {
                    Text(
                        text = stringResource(R.string.members_count, state.total),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(
                            start = UnefySpacing.screen,
                            end = UnefySpacing.screen,
                            top = UnefySpacing.xs,
                            bottom = UnefySpacing.sm,
                        ),
                    )
                }
                items(state.members, key = { it.id }) { member ->
                    MemberRow(member, onClick = { onMemberClick(member.id) })
                    UnefyRowDivider()
                }
                if (state.isLoadingMore) item(key = "more") { UnefyLoadMoreFooter() }
            }
        }
    }
}

@Composable
private fun MemberRow(member: Member, onClick: () -> Unit) {
    Row(
        // The Material state layer, not a scale animation. A list row that
        // shrinks under the finger is a web idiom; Android expresses press with
        // a ripple over the row's own bounds.
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.md),
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.md),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Surface(
            shape = CircleShape,
            color = MaterialTheme.colorScheme.surfaceContainerHighest,
            modifier = Modifier.size(AVATAR_SIZE),
        ) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(
                    text = member.initials,
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                )
            }
        }

        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(
                text = member.displayName,
                style = MaterialTheme.typography.titleMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = member.memberNumber,
                style = UnefyNumericTextStyle,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        StatusPill(member.status)
    }
}

/**
 * A tonal pill rather than coloured text. In a palette this quiet, a bare
 * coloured word reads as an accident; a container reads as a decision.
 */
@Composable
private fun StatusPill(status: MemberStatus) {
    val extended = LocalUnefyColors.current
    val (label, container, content) = when (status) {
        MemberStatus.ACTIVE -> Triple(
            R.string.member_status_active,
            extended.successContainer,
            extended.onSuccessContainer,
        )
        MemberStatus.PENDING -> Triple(
            R.string.member_status_pending,
            extended.warningContainer,
            extended.onWarningContainer,
        )
        MemberStatus.RESIGNED -> Triple(
            R.string.member_status_resigned,
            MaterialTheme.colorScheme.errorContainer,
            MaterialTheme.colorScheme.onErrorContainer,
        )
        MemberStatus.INACTIVE, MemberStatus.UNKNOWN -> Triple(
            if (status == MemberStatus.INACTIVE) {
                R.string.member_status_inactive
            } else {
                R.string.member_status_unknown
            },
            MaterialTheme.colorScheme.surfaceContainerHighest,
            MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }

    Surface(shape = CircleShape, color = container) {
        Text(
            text = stringResource(label),
            style = MaterialTheme.typography.labelMedium,
            color = content,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
        )
    }
}

/**
 * Skeleton rows matched to the geometry of [MemberRow] — a placeholder that does
 * not match what it becomes is worse than none. Spinners are forbidden here.
 */
private fun LazyListScope.membersSkeleton() {
    items(SKELETON_ROWS) { MemberSkeletonRow() }
}

@Composable
private fun MemberSkeletonRow() {
    val transition = rememberInfiniteTransition(label = "skeleton")
    val color by transition.animateColor(
        initialValue = MaterialTheme.colorScheme.surfaceContainer,
        targetValue = MaterialTheme.colorScheme.surfaceContainerHighest,
        animationSpec = infiniteRepeatable(UnefyMotion.shimmer(), RepeatMode.Reverse),
        label = "skeletonColor",
    )

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.md),
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.md),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(AVATAR_SIZE).background(color, CircleShape))
        Column(verticalArrangement = Arrangement.spacedBy(UnefySpacing.xs)) {
            Box(Modifier.width(168.dp).height(16.dp).background(color, SkeletonShape))
            Box(Modifier.width(72.dp).height(12.dp).background(color, SkeletonShape))
        }
    }
    UnefyRowDivider()
}

@Composable
private fun ErrorState(error: ApiError, onRetry: () -> Unit, modifier: Modifier = Modifier) {
    val (title, body) = when (error) {
        is ApiError.Network -> R.string.error_network_title to R.string.error_network_body
        ApiError.Forbidden -> R.string.error_forbidden_title to R.string.error_forbidden_body
        else -> R.string.error_generic_title to R.string.error_generic_body
    }
    CenteredMessage(
        title = stringResource(title),
        body = stringResource(body),
        modifier = modifier,
        action = { OutlinedButton(onClick = onRetry) { Text(stringResource(R.string.members_retry)) } },
    )
}

@Composable
private fun EmptyState(hasQuery: Boolean, modifier: Modifier = Modifier) {
    CenteredMessage(
        title = stringResource(
            if (hasQuery) R.string.members_no_matches_title else R.string.members_empty_title,
        ),
        body = stringResource(
            if (hasQuery) R.string.members_no_matches_body else R.string.members_empty_body,
        ),
        modifier = modifier,
    )
}

@Composable
private fun CenteredMessage(
    title: String,
    body: String,
    modifier: Modifier = Modifier,
    action: (@Composable () -> Unit)? = null,
) {
    Column(
        modifier = modifier.fillMaxWidth().padding(UnefySpacing.lg),
        verticalArrangement = Arrangement.spacedBy(UnefySpacing.sm, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(text = title, style = MaterialTheme.typography.headlineSmall)
        Text(
            text = body,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        action?.invoke()
    }
}

private val SkeletonShape = RoundedCornerShape(6.dp)
private val AVATAR_SIZE = 44.dp

private const val SKELETON_ROWS = 8

/** Empty and error states fill what is left below the heading, not the window. */
private const val FILL_BELOW_HEADING = 0.7f

@Preview
@Composable
private fun MembersLoadingPreview() {
    UnefyTheme { MembersScreen(state = MembersUiState.Loading, clubName = "SV Musterhausen") }
}

@Preview
@Composable
private fun MembersEmptyPreview() {
    UnefyTheme { MembersScreen(state = MembersUiState.Content(emptyList())) }
}
