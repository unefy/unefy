package com.unefy.feature.members

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.component.UNEFY_STATE_FILL
import com.unefy.core.designsystem.component.UnefyCenteredState
import com.unefy.core.designsystem.component.UnefyListScaffold
import com.unefy.core.designsystem.component.UnefyRowDivider
import com.unefy.core.designsystem.theme.UnefyFormat
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** What just happened, said once and then cleared. */
enum class ConsentNotice {
    Granted,
    Withdrawn,

    /** Nothing was recorded. Deliberately not softened — see [MyConsentsViewModel.set]. */
    Failed,
}

data class MyConsentsUiState(
    val loading: Boolean = true,
    val overview: ConsentOverview? = null,
    val error: ApiError? = null,
    /** The kind being written right now; its switch waits rather than lying. */
    val saving: String? = null,
    val notice: ConsentNotice? = null,
)

/**
 * What the member has allowed, and the ledger behind it.
 *
 * Nothing here is optimistic and nothing is queued. A withdrawal that shows as
 * done while it sits in a queue on the member's own phone is the one outcome
 * this screen must never produce: the club goes on sending the newsletter, the
 * member believes they have stopped it, and both are looking at the same app.
 * So the switch moves when the server has recorded it, or says that it did not.
 */
@HiltViewModel
class MyConsentsViewModel @Inject constructor(
    private val repository: MembersRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(MyConsentsUiState())
    val uiState: StateFlow<MyConsentsUiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun load() {
        _uiState.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            _uiState.value = when (val result = repository.myConsents()) {
                is ApiResult.Success -> MyConsentsUiState(loading = false, overview = result.data)
                is ApiResult.Failure -> MyConsentsUiState(loading = false, error = result.error)
            }
        }
    }

    /**
     * Give or withdraw one consent.
     *
     * The answer the server sends back is what the screen then shows, rather
     * than the value that was tapped: the two agree today, and if they ever
     * stop agreeing the member should see the record, not the request.
     */
    fun set(kind: String, granted: Boolean) {
        if (_uiState.value.saving != null) return
        _uiState.update { it.copy(saving = kind, notice = null) }

        viewModelScope.launch {
            when (val result = repository.recordConsent(kind, granted)) {
                is ApiResult.Success -> _uiState.update { state ->
                    state.copy(
                        saving = null,
                        overview = state.overview?.applying(result.data),
                        notice = if (result.data.granted) {
                            ConsentNotice.Granted
                        } else {
                            ConsentNotice.Withdrawn
                        },
                    )
                }

                is ApiResult.Failure -> _uiState.update {
                    it.copy(saving = null, notice = ConsentNotice.Failed)
                }
            }
        }
    }

    fun onNoticeShown() = _uiState.update { it.copy(notice = null) }
}

/**
 * The new entry folded into the overview, without asking again.
 *
 * The ledger is append-only, so the client can do this exactly: the entry the
 * server returned *is* the new current answer, and it goes on top of the trail.
 */
private fun ConsentOverview.applying(entry: ConsentEntry) = ConsentOverview(
    current = current.map { state ->
        if (state.kind == entry.kind) {
            ConsentState(
                kind = entry.kind,
                granted = entry.granted,
                since = entry.recordedAt,
                source = entry.source,
            )
        } else {
            state
        }
    },
    history = listOf(entry) + history,
)

@Composable
fun MyConsentsRoute(
    onBack: () -> Unit,
    viewModel: MyConsentsViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    MyConsentsScreen(
        state = state,
        onBack = onBack,
        onRetry = viewModel::load,
        onSet = viewModel::set,
        onNoticeShown = viewModel::onNoticeShown,
    )
}

@Composable
fun MyConsentsScreen(
    state: MyConsentsUiState,
    onBack: () -> Unit = {},
    onRetry: () -> Unit = {},
    onSet: (kind: String, granted: Boolean) -> Unit = { _, _ -> },
    onNoticeShown: () -> Unit = {},
) {
    UnefyListScaffold(
        title = stringResource(R.string.consents_title),
        navigationIcon = {
            IconButton(onClick = onBack) {
                Icon(
                    painter = painterResource(DesignR.drawable.ic_arrow_back),
                    contentDescription = stringResource(R.string.consents_back),
                )
            }
        },
        // A snackbar carries all three outcomes, the failure included: the
        // switch never moved on its own, so a member who is told nothing was
        // saved is looking at a switch that agrees with the sentence.
        message = state.notice?.let { notice ->
            stringResource(
                when (notice) {
                    ConsentNotice.Granted -> R.string.consents_granted
                    ConsentNotice.Withdrawn -> R.string.consents_withdrawn
                    ConsentNotice.Failed -> R.string.consents_failed
                },
            )
        },
        onMessageShown = onNoticeShown,
    ) {
        when {
            state.error != null -> item("error") {
                UnefyCenteredState(
                    title = if (state.error is ApiError.NotFound) {
                        stringResource(R.string.profile_none_title)
                    } else {
                        stringResource(R.string.error_generic_title)
                    },
                    body = if (state.error is ApiError.NotFound) {
                        stringResource(R.string.profile_none_body)
                    } else {
                        null
                    },
                    modifier = Modifier.fillParentMaxHeight(UNEFY_STATE_FILL),
                    action = if (state.error is ApiError.NotFound) {
                        null
                    } else {
                        {
                            OutlinedButton(onClick = onRetry) {
                                Text(stringResource(R.string.members_retry))
                            }
                        }
                    },
                )
            }

            state.overview != null -> {
                item("intro") {
                    Text(
                        text = stringResource(R.string.consents_intro),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(
                            horizontal = UnefySpacing.screen,
                            vertical = UnefySpacing.sm,
                        ),
                    )
                }

                items(state.overview.current.size, key = { "kind-${it}" }) { index ->
                    val consent = state.overview.current[index]
                    ConsentRow(
                        consent = consent,
                        busy = state.saving == consent.kind,
                        // One at a time: a second write while the first is in
                        // flight would land in the ledger in whichever order the
                        // network chose, and the ledger is the proof.
                        enabled = state.saving == null,
                        onSet = { granted -> onSet(consent.kind, granted) },
                    )
                    UnefyRowDivider()
                }

                item("history-title") {
                    Text(
                        text = stringResource(R.string.consents_history),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(
                            start = UnefySpacing.screen,
                            end = UnefySpacing.screen,
                            top = UnefySpacing.lg,
                            bottom = UnefySpacing.sm,
                        ),
                    )
                }

                if (state.overview.history.isEmpty()) {
                    item("history-empty") {
                        Text(
                            text = stringResource(R.string.consents_no_history),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(
                                horizontal = UnefySpacing.screen,
                                vertical = UnefySpacing.sm,
                            ),
                        )
                    }
                } else {
                    items(state.overview.history.size, key = { state.overview.history[it].id }) {
                        HistoryRow(state.overview.history[it])
                        UnefyRowDivider()
                    }
                    item("ledger-note") {
                        Text(
                            text = stringResource(R.string.consents_ledger_note),
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(
                                horizontal = UnefySpacing.screen,
                                vertical = UnefySpacing.md,
                            ),
                        )
                    }
                }
            }
        }
    }
}

/**
 * One consent, with the answer as a switch and the state said in words below.
 *
 * The words matter more than they look: a switch has two positions and this has
 * three answers. "Noch nicht gefragt" is not a no, and an off switch on its own
 * would claim it was.
 */
@Composable
private fun ConsentRow(
    consent: ConsentState,
    busy: Boolean,
    enabled: Boolean,
    onSet: (Boolean) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.sm),
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.md),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(UnefySpacing.xs),
        ) {
            Text(text = consentLabel(consent.kind), style = MaterialTheme.typography.bodyLarge)
            Text(
                text = consentDescription(consent.kind),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = when {
                    busy -> stringResource(R.string.consents_saving)
                    consent.granted == null -> stringResource(R.string.consents_never_asked)
                    consent.since != null -> stringResource(
                        if (consent.granted) R.string.consents_yes_since else R.string.consents_no_since,
                        UnefyFormat.date(consent.since),
                    )

                    consent.granted -> stringResource(R.string.consents_yes)
                    else -> stringResource(R.string.consents_no)
                },
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        Switch(
            checked = consent.granted == true,
            onCheckedChange = onSet,
            enabled = enabled,
        )
    }
}

@Composable
private fun HistoryRow(entry: ConsentEntry) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.sm),
        verticalArrangement = Arrangement.spacedBy(UnefySpacing.xs),
    ) {
        Text(
            text = "${consentLabel(entry.kind)} · " + stringResource(
                if (entry.granted) R.string.consents_yes else R.string.consents_no,
            ),
            style = MaterialTheme.typography.bodyLarge,
        )
        Text(
            text = "${UnefyFormat.dateTime(entry.recordedAt)} · ${consentSource(entry.source)}",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        entry.note?.let { note ->
            Text(
                text = note,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

/**
 * The kinds are a backend constant, not an enum on the wire, so an unknown one
 * is shown by its key rather than dropped: a club that gains a fourth consent
 * should see it here before the app has heard of it.
 */
@Composable
private fun consentLabel(kind: String): String = when (kind) {
    "photos" -> stringResource(R.string.consent_photos)
    "newsletter" -> stringResource(R.string.consent_newsletter)
    "directory" -> stringResource(R.string.consent_directory)
    else -> kind
}

@Composable
private fun consentDescription(kind: String): String = when (kind) {
    "photos" -> stringResource(R.string.consent_photos_body)
    "newsletter" -> stringResource(R.string.consent_newsletter_body)
    "directory" -> stringResource(R.string.consent_directory_body)
    else -> ""
}

@Composable
private fun consentSource(source: String): String = when (source) {
    "application" -> stringResource(R.string.consent_source_application)
    "self" -> stringResource(R.string.consent_source_self)
    "board" -> stringResource(R.string.consent_source_board)
    else -> source
}

@Preview
@Composable
private fun MyConsentsPreview() {
    UnefyTheme {
        MyConsentsScreen(
            state = MyConsentsUiState(
                loading = false,
                overview = ConsentOverview(
                    current = listOf(
                        ConsentState("photos", true, "2026-03-01T18:00:00Z", "self"),
                        ConsentState("newsletter", false, "2026-03-01T18:00:00Z", "board"),
                        ConsentState("directory", null, null, null),
                    ),
                    history = listOf(
                        ConsentEntry(
                            id = "1",
                            kind = "photos",
                            granted = true,
                            recordedAt = "2026-03-01T18:00:00Z",
                            source = "self",
                            note = null,
                        ),
                    ),
                ),
            ),
        )
    }
}
