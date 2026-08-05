package com.unefy.feature.competitions

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.unefy.core.designsystem.component.Field
import com.unefy.core.designsystem.component.UnefyDetailScaffold
import com.unefy.core.designsystem.component.UnefyDetailSection
import com.unefy.core.designsystem.theme.UnefyFormat
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.Competition
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn

sealed interface CompetitionDetailUiState {
    data object Loading : CompetitionDetailUiState
    data class Content(val competition: Competition) : CompetitionDetailUiState
}

/**
 * One competition, straight from the mirror — the whole screen works offline.
 *
 * No remote fetch: unlike a member's bank details there is nothing the mirror
 * deliberately leaves out, and unlike the scoreboard nothing here is a live
 * aggregate. The row the person just tapped is on disk; showing anything
 * slower would be a regression.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class CompetitionDetailViewModel @Inject constructor(
    private val repository: CompetitionsRepository,
) : ViewModel() {

    private val competitionId = MutableStateFlow<String?>(null)

    val uiState: StateFlow<CompetitionDetailUiState> = competitionId
        .flatMapLatest { id -> id?.let(repository::byIdStream) ?: flowOf(null) }
        .map { competition ->
            competition
                ?.let(CompetitionDetailUiState::Content)
                ?: CompetitionDetailUiState.Loading
        }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(SUBSCRIPTION_GRACE_MS),
            initialValue = CompetitionDetailUiState.Loading,
        )

    fun load(id: String) {
        competitionId.value = id
    }

    private companion object {
        const val SUBSCRIPTION_GRACE_MS = 5_000L
    }
}

@Composable
fun CompetitionDetailRoute(
    competitionId: String,
    competitionName: String,
    onBack: () -> Unit,
    onOpenScoreboard: () -> Unit,
    viewModel: CompetitionDetailViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    LaunchedEffect(competitionId) { viewModel.load(competitionId) }
    CompetitionDetailScreen(
        state = state,
        competitionName = competitionName,
        onBack = onBack,
        onOpenScoreboard = onOpenScoreboard,
    )
}

@Composable
fun CompetitionDetailScreen(
    state: CompetitionDetailUiState,
    /** From the navigation key, so the header never waits for the mirror. */
    competitionName: String,
    onBack: () -> Unit = {},
    onOpenScoreboard: () -> Unit = {},
) {
    UnefyDetailScaffold(
        collapsedTitle = competitionName,
        onBack = onBack,
    ) {
        val competition = (state as? CompetitionDetailUiState.Content)?.competition

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(
                    start = UnefySpacing.screen,
                    end = UnefySpacing.screen,
                    top = UnefySpacing.sm,
                    bottom = UnefySpacing.md,
                ),
            verticalArrangement = Arrangement.spacedBy(UnefySpacing.xs),
        ) {
            competition?.let {
                Text(
                    text = dateRange(it),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(text = competitionName, style = MaterialTheme.typography.headlineSmall)
        }

        // The one filled action on the screen: the ranking is what people
        // open a competition for; everything below is reference.
        Button(
            onClick = onOpenScoreboard,
            modifier = Modifier.padding(horizontal = UnefySpacing.screen),
        ) { Text(stringResource(R.string.competition_detail_scoreboard)) }

        competition ?: return@UnefyDetailScaffold

        competition.description?.takeIf { it.isNotBlank() }?.let { description ->
            Text(
                text = stringResource(R.string.competition_detail_section_description),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(
                    start = UnefySpacing.screen,
                    end = UnefySpacing.screen,
                    top = UnefySpacing.lg,
                    bottom = UnefySpacing.sm,
                ),
            )
            Text(
                text = description,
                style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.padding(
                    horizontal = UnefySpacing.screen,
                    vertical = UnefySpacing.sm,
                ),
            )
        }

        UnefyDetailSection(
            title = stringResource(R.string.competition_detail_section_scoring),
            fields = listOf(
                Field(
                    label = stringResource(R.string.competition_detail_unit),
                    value = competition.scoringUnit,
                ),
                Field(
                    label = stringResource(R.string.competition_detail_mode),
                    value = stringResource(
                        if (competition.highestWins) {
                            R.string.competition_detail_mode_highest
                        } else {
                            R.string.competition_detail_mode_lowest
                        },
                    ),
                ),
                Field(
                    label = stringResource(R.string.competition_detail_type),
                    value = competitionTypeLabel(competition.type),
                ),
            ),
        )

        if (competition.disciplines.isNotEmpty()) {
            Text(
                text = stringResource(
                    R.string.competition_detail_section_disciplines,
                    competition.disciplines.size,
                ),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(
                    start = UnefySpacing.screen,
                    end = UnefySpacing.screen,
                    top = UnefySpacing.lg,
                    bottom = UnefySpacing.sm,
                ),
            )
            competition.disciplines.forEach { discipline ->
                Text(
                    text = discipline,
                    style = MaterialTheme.typography.bodyLarge,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(
                            horizontal = UnefySpacing.screen,
                            vertical = UnefySpacing.sm,
                        ),
                )
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            }
        }
    }
}

@Composable
private fun competitionTypeLabel(type: String?): String? = when (type) {
    "league" -> stringResource(R.string.competition_type_league)
    "competition" -> stringResource(R.string.competition_type_competition)
    "training" -> stringResource(R.string.competition_type_training)
    else -> null
}

@Preview
@Composable
private fun CompetitionDetailPreview() {
    UnefyTheme {
        CompetitionDetailScreen(
            state = CompetitionDetailUiState.Content(
                Competition(
                    id = "1",
                    name = "Vereinsmeisterschaft 2026",
                    description = "Alle Durchgänge zählen, die besten drei kommen in die Wertung.",
                    type = "competition",
                    startDate = "2026-03-07",
                    endDate = "2026-09-26",
                    scoringUnit = "Ringe",
                    scoringMode = "highest_wins",
                    disciplines = listOf("BDS KK-Pistole 25m", "BDS Luftgewehr 10m"),
                ),
            ),
            competitionName = "Vereinsmeisterschaft 2026",
        )
    }
}
