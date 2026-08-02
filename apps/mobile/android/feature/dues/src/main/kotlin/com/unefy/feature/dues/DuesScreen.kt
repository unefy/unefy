package com.unefy.feature.dues

import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.unefy.core.designsystem.theme.LocalUnefyColors
import com.unefy.core.designsystem.theme.UnefyFormat
import com.unefy.core.designsystem.theme.UnefyMoneyTextStyle
import com.unefy.core.designsystem.component.UnefyListScaffold
import com.unefy.core.designsystem.component.UnefyRowDivider
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.DuesEntry
import com.unefy.core.model.DuesStatus
import com.unefy.core.model.DuesSummary

@Composable
fun DuesRoute(
    actions: @Composable RowScope.() -> Unit = {},
    viewModel: DuesViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    DuesScreen(
        state = state,
        actions = actions,
        onFilterChange = viewModel::onFilterChange,
        onRetry = viewModel::retry,
    )
}

@Composable
fun DuesScreen(
    state: DuesUiState,
    @StringRes titleRes: Int = R.string.dues_title,
    /** False on the own-dues screen, where every row is the same person. */
    showMemberName: Boolean = true,
    actions: @Composable RowScope.() -> Unit = {},
    onFilterChange: (DuesFilter) -> Unit = {},
    onRetry: () -> Unit = {},
) {
    UnefyListScaffold(title = stringResource(titleRes), actions = actions) {
        when (state) {
            DuesUiState.Loading -> Unit

            is DuesUiState.Failure -> item {
                Column(
                    modifier = Modifier
                        .fillParentMaxHeight(FILL_BELOW_HEADING)
                        .fillMaxWidth()
                        .padding(UnefySpacing.lg),
                    verticalArrangement = Arrangement.spacedBy(
                        UnefySpacing.sm,
                        Alignment.CenterVertically,
                    ),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(
                        text = stringResource(R.string.dues_error_title),
                        style = MaterialTheme.typography.headlineSmall,
                    )
                    OutlinedButton(onClick = onRetry) {
                        Text(stringResource(R.string.dues_retry))
                    }
                }
            }

            is DuesUiState.Content -> {
                state.summary?.let { summary -> item(key = "summary") { SummaryRow(summary) } }

                item(key = "filters") {
                    Row(
                        modifier = Modifier.padding(
                            horizontal = UnefySpacing.screen,
                            vertical = UnefySpacing.sm,
                        ),
                        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
                    ) {
                        DuesFilter.entries.forEach { filter ->
                            FilterChip(
                                selected = state.filter == filter,
                                onClick = { onFilterChange(filter) },
                                label = { Text(stringResource(filter.labelRes())) },
                            )
                        }
                    }
                }

                items(state.visible, key = { it.id }) { entry ->
                    DuesRow(entry, showMemberName)
                    // Dues rows have no leading avatar, so the divider starts at
                    // the screen margin rather than the row's text inset.
                    UnefyRowDivider(startInset = UnefySpacing.screen)
                }
            }
        }
    }
}

/** Empty and error states fill what is left below the heading, not the window. */
private const val FILL_BELOW_HEADING = 0.7f

/**
 * Two figures, not a chart. The question this screen answers first is "how much
 * is still outstanding" — a number answers it faster than any visualisation.
 */
@Composable
private fun SummaryRow(summary: DuesSummary) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(
                start = UnefySpacing.screen,
                end = UnefySpacing.screen,
                top = UnefySpacing.sm,
                bottom = UnefySpacing.sm,
            ),
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.md),
    ) {
        SummaryTile(
            label = stringResource(R.string.dues_open, summary.openCount),
            value = UnefyFormat.money(summary.openAmount),
            emphasised = summary.openCount > 0,
            modifier = Modifier.weight(1f),
        )
        SummaryTile(
            label = stringResource(R.string.dues_paid, summary.paidCount),
            value = UnefyFormat.money(summary.paidAmount),
            emphasised = false,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun SummaryTile(
    label: String,
    value: String,
    emphasised: Boolean,
    modifier: Modifier = Modifier,
) {
    val extended = LocalUnefyColors.current
    Surface(
        modifier = modifier,
        shape = MaterialTheme.shapes.large,
        color = if (emphasised) {
            extended.warningContainer
        } else {
            MaterialTheme.colorScheme.surfaceContainer
        },
    ) {
        Column(
            modifier = Modifier.padding(UnefySpacing.md),
            verticalArrangement = Arrangement.spacedBy(UnefySpacing.xs),
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.labelMedium,
                color = if (emphasised) {
                    extended.onWarningContainer
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                },
            )
            Text(
                text = value,
                style = MaterialTheme.typography.headlineSmall,
                color = if (emphasised) {
                    extended.onWarningContainer
                } else {
                    MaterialTheme.colorScheme.onSurface
                },
            )
        }
    }
}

@Composable
private fun DuesRow(entry: DuesEntry, showMemberName: Boolean) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.md),
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.md),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(
                text = if (showMemberName) entry.memberName else entry.feeName,
                style = MaterialTheme.typography.titleMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (showMemberName) {
                Text(
                    text = entry.feeName,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            entry.dueDate?.let {
                Text(
                    text = stringResource(R.string.dues_due, UnefyFormat.date(it)),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        Column(horizontalAlignment = Alignment.End) {
            Text(
                text = UnefyFormat.money(entry.amount),
                style = UnefyMoneyTextStyle,
            )
            StatusPill(entry.status)
        }
    }
}

@Composable
private fun StatusPill(status: DuesStatus) {
    val extended = LocalUnefyColors.current
    val (label, container, content) = when (status) {
        DuesStatus.PAID -> Triple(
            R.string.dues_status_paid,
            extended.successContainer,
            extended.onSuccessContainer,
        )
        DuesStatus.OVERDUE -> Triple(
            R.string.dues_status_overdue,
            MaterialTheme.colorScheme.errorContainer,
            MaterialTheme.colorScheme.onErrorContainer,
        )
        DuesStatus.OPEN -> Triple(
            R.string.dues_status_open,
            extended.warningContainer,
            extended.onWarningContainer,
        )
        DuesStatus.CANCELLED, DuesStatus.UNKNOWN -> Triple(
            if (status == DuesStatus.CANCELLED) {
                R.string.dues_status_cancelled
            } else {
                R.string.dues_status_unknown
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

private fun DuesFilter.labelRes() = when (this) {
    DuesFilter.ALL -> R.string.dues_filter_all
    DuesFilter.OPEN -> R.string.dues_filter_open
    DuesFilter.PAID -> R.string.dues_filter_paid
}

@Preview
@Composable
private fun DuesPreview() {
    UnefyTheme {
        DuesScreen(
            state = DuesUiState.Content(
                summary = DuesSummary(5, "600.00", 34, "4440.00"),
                entries = listOf(
                    DuesEntry(
                        id = "1",
                        memberId = "m1",
                        memberName = "Claudia Fischer",
                        feeName = "Erwachsene",
                        amount = "120.00",
                        dueDate = "2025-01-31",
                        status = DuesStatus.PAID,
                        paidAt = null,
                    ),
                ),
                filter = DuesFilter.ALL,
            ),
        )
    }
}
