package com.unefy.feature.competitions

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
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
import com.unefy.core.designsystem.component.UnefyListScaffold
import com.unefy.core.designsystem.component.UnefyRowDivider
import com.unefy.core.designsystem.theme.UnefyNumericTextStyle
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.Scoreboard
import com.unefy.core.model.ScoreboardRow

@Composable
fun ScoreboardRoute(
    competitionId: String,
    competitionName: String,
    onBack: () -> Unit,
    viewModel: ScoreboardViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val disciplines by viewModel.disciplines.collectAsStateWithLifecycle()
    val selectedDiscipline by viewModel.selectedDiscipline.collectAsStateWithLifecycle()
    LaunchedEffect(competitionId) { viewModel.load(competitionId) }
    ScoreboardScreen(
        state = state,
        competitionName = competitionName,
        disciplines = disciplines,
        selectedDiscipline = selectedDiscipline,
        onBack = onBack,
        onRefresh = viewModel::refresh,
        onSelectDiscipline = viewModel::selectDiscipline,
        onMessageShown = viewModel::onMessageShown,
    )
}

@Composable
fun ScoreboardScreen(
    state: ScoreboardUiState,
    competitionName: String,
    disciplines: List<String> = emptyList(),
    selectedDiscipline: String? = null,
    onBack: () -> Unit = {},
    onRefresh: () -> Unit = {},
    onSelectDiscipline: (String?) -> Unit = {},
    onMessageShown: () -> Unit = {},
) {
    val content = state as? ScoreboardUiState.Content
    val subtitle = content?.scoreboard?.let { board ->
        stringResource(R.string.scoreboard_subtitle, board.rows.size, board.unit)
    }

    UnefyListScaffold(
        title = competitionName,
        subtitle = subtitle,
        navigationIcon = {
            IconButton(onClick = onBack) {
                Icon(
                    painter = painterResource(DesignR.drawable.ic_arrow_back),
                    contentDescription = stringResource(R.string.scoreboard_back),
                )
            }
        },
        isRefreshing = content?.isRefreshing == true,
        onRefresh = onRefresh,
        message = stringResource(DesignR.string.refresh_failed)
            .takeIf { content?.refreshFailed == true },
        onMessageShown = onMessageShown,
    ) {
        // One chip per discipline plus "Gesamt" — only when there is a choice
        // to make. A single-discipline competition has nothing to filter.
        if (disciplines.size > 1) {
            item(key = "disciplines") {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState())
                        .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.xs),
                ) {
                    FilterChip(
                        selected = selectedDiscipline == null,
                        onClick = { onSelectDiscipline(null) },
                        label = { Text(stringResource(R.string.scoreboard_all_disciplines)) },
                    )
                    disciplines.forEach { discipline ->
                        FilterChip(
                            selected = discipline == selectedDiscipline,
                            onClick = { onSelectDiscipline(discipline) },
                            label = { Text(discipline) },
                        )
                    }
                }
            }
        }

        when (state) {
            ScoreboardUiState.Loading -> Unit

            is ScoreboardUiState.Failure -> item {
                Centered(
                    title = stringResource(R.string.competitions_error_title),
                    body = stringResource(R.string.scoreboard_error_body),
                    modifier = Modifier.fillParentMaxHeight(FILL_BELOW_HEADER),
                )
            }

            is ScoreboardUiState.Content -> if (state.scoreboard.rows.isEmpty()) {
                item {
                    Centered(
                        title = stringResource(R.string.scoreboard_empty_title),
                        body = stringResource(R.string.scoreboard_empty_body),
                        modifier = Modifier.fillParentMaxHeight(FILL_BELOW_HEADER),
                    )
                }
            } else {
                items(state.scoreboard.rows, key = { it.memberId }) { row ->
                    ScoreRow(row = row, unit = state.scoreboard.unit)
                    UnefyRowDivider()
                }
            }
        }
    }
}

@Composable
private fun ScoreRow(row: ScoreboardRow, unit: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.md),
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.md),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RankBadge(row.rank)

        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = row.memberName,
                style = MaterialTheme.typography.titleMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = stringResource(
                    R.string.scoreboard_detail,
                    formatScore(row.bestScore),
                    formatScore(row.averageScore),
                    row.entryCount,
                ),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        Column(horizontalAlignment = Alignment.End) {
            Text(text = formatScore(row.totalScore), style = UnefyNumericTextStyle)
            Text(
                text = unit,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

/**
 * The rank, emphasised for the podium only.
 *
 * With no brand hue available, first place is marked by weight and a filled
 * container rather than gold — which the palette could not express anyway.
 */
@Composable
private fun RankBadge(rank: Int) {
    val podium = rank <= PODIUM
    Surface(
        shape = CircleShape,
        // primary, not primaryContainer: in dark mode the container is #262626
        // against a #171717 surface, so the podium marking was invisible. The
        // filled variant inverts — near-white on near-black — which is the only
        // strong emphasis a monochrome palette has.
        color = if (podium) {
            MaterialTheme.colorScheme.primary
        } else {
            MaterialTheme.colorScheme.surfaceContainer
        },
        modifier = Modifier.size(BADGE_SIZE),
    ) {
        Box(contentAlignment = Alignment.Center) {
            Text(
                text = rank.toString(),
                style = UnefyNumericTextStyle,
                color = if (podium) {
                    MaterialTheme.colorScheme.onPrimary
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                },
            )
        }
    }
}

/** Scores arrive as doubles but are whole rings in practice — no stray ".0". */
private fun formatScore(value: Double): String =
    if (value % 1.0 == 0.0) value.toInt().toString() else "%.1f".format(value)

private val BADGE_SIZE = 36.dp
private const val PODIUM = 3

@Preview
@Composable
private fun ScoreboardPreview() {
    UnefyTheme {
        ScoreboardScreen(
            state = ScoreboardUiState.Content(
                Scoreboard(
                    unit = "Ringe",
                    highestWins = true,
                    rows = listOf(
                        ScoreboardRow(1, "1", "Birgit Klein", 1040.0, 358.0, 346.67, 3),
                        ScoreboardRow(2, "2", "Stefan Weber", 1028.0, 346.0, 342.67, 3),
                        ScoreboardRow(4, "4", "Michael Schneider", 1027.0, 364.0, 342.33, 3),
                    ),
                ),
            ),
            competitionName = "Vereinsmeisterschaft 2026",
        )
    }
}
