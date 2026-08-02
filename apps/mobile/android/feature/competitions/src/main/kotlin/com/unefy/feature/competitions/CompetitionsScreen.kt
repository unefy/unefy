package com.unefy.feature.competitions

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.component.UnefyListScaffold
import com.unefy.core.designsystem.component.UnefyLoadMoreFooter
import com.unefy.core.designsystem.component.UnefyRowDivider
import com.unefy.core.designsystem.theme.UnefyFormat
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.Competition

@Composable
fun CompetitionsRoute(
    onCompetitionClick: (String, String) -> Unit,
    actions: @Composable RowScope.() -> Unit = {},
    viewModel: CompetitionsViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    CompetitionsScreen(
        state = state,
        actions = actions,
        onCompetitionClick = onCompetitionClick,
        onRetry = viewModel::retry,
        onRefresh = viewModel::refresh,
        onLoadMore = viewModel::loadMore,
        onMessageShown = viewModel::onMessageShown,
    )
}

@Composable
fun CompetitionsScreen(
    state: CompetitionsUiState,
    actions: @Composable RowScope.() -> Unit = {},
    onCompetitionClick: (String, String) -> Unit = { _, _ -> },
    onRetry: () -> Unit = {},
    onRefresh: () -> Unit = {},
    onLoadMore: () -> Unit = {},
    onMessageShown: () -> Unit = {},
) {
    val content = state as? CompetitionsUiState.Content

    UnefyListScaffold(
        title = stringResource(R.string.competitions_title),
        actions = actions,
        isRefreshing = content?.isRefreshing == true,
        onRefresh = onRefresh,
        onLoadMore = onLoadMore,
        message = stringResource(DesignR.string.refresh_failed)
            .takeIf { content?.refreshFailed == true },
        onMessageShown = onMessageShown,
    ) {
        when (state) {
            CompetitionsUiState.Loading -> Unit

            is CompetitionsUiState.Failure -> item {
                Centered(
                    title = stringResource(R.string.competitions_error_title),
                    body = stringResource(R.string.competitions_error_body),
                    modifier = Modifier.fillParentMaxHeight(FILL_BELOW_HEADER),
                    action = {
                        OutlinedButton(onClick = onRetry) {
                            Text(stringResource(R.string.competitions_retry))
                        }
                    },
                )
            }

            is CompetitionsUiState.Content -> if (state.competitions.isEmpty()) {
                item {
                    Centered(
                        title = stringResource(R.string.competitions_empty_title),
                        body = stringResource(R.string.competitions_empty_body),
                        modifier = Modifier.fillParentMaxHeight(FILL_BELOW_HEADER),
                    )
                }
            } else {
                items(state.competitions, key = { it.id }) { competition ->
                    CompetitionRow(
                        competition = competition,
                        onClick = { onCompetitionClick(competition.id, competition.name) },
                    )
                    UnefyRowDivider(startInset = UnefySpacing.screen)
                }
                if (state.isLoadingMore) item(key = "more") { UnefyLoadMoreFooter() }
            }
        }
    }
}

@Composable
private fun CompetitionRow(competition: Competition, onClick: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.md),
        verticalArrangement = Arrangement.spacedBy(UnefySpacing.xs),
    ) {
        Text(
            text = dateRange(competition),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = competition.name,
            style = MaterialTheme.typography.titleMedium,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        if (competition.disciplines.isNotEmpty()) {
            Text(
                // Joined rather than a chip row: on a list row the disciplines
                // are context, not something to tap.
                text = competition.disciplines.joinToString(" · "),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun dateRange(competition: Competition): String {
    val start = UnefyFormat.date(competition.startDate)
    val end = competition.endDate?.let(UnefyFormat::date)
    return if (end.isNullOrBlank() || end == start) start else "$start – $end"
}

@Composable
internal fun Centered(
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
        Text(title, style = MaterialTheme.typography.headlineSmall)
        Text(
            text = body,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        action?.invoke()
    }
}

internal const val FILL_BELOW_HEADER = 0.7f

@Preview
@Composable
private fun CompetitionsPreview() {
    UnefyTheme {
        CompetitionsScreen(
            state = CompetitionsUiState.Content(
                listOf(
                    Competition(
                        id = "1",
                        name = "Vereinsmeisterschaft 2026",
                        description = null,
                        type = "competition",
                        startDate = "2026-03-07",
                        endDate = "2026-09-26",
                        scoringUnit = "Ringe",
                        scoringMode = "highest_wins",
                        disciplines = listOf("BDS KK-Pistole 25m", "BDS Luftgewehr 10m"),
                    ),
                ),
            ),
        )
    }
}
