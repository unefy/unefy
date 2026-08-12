package com.unefy.feature.documents

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import com.unefy.core.designsystem.component.UnefyPill
import com.unefy.core.designsystem.component.UnefyRowDivider
import com.unefy.core.designsystem.theme.LocalUnefyColors
import com.unefy.core.designsystem.theme.UnefyFormat
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/** Said once after an issue, then cleared. */
enum class DocumentNotice {
    Issued,
    Failed,

    /** The club has written no wording yet — the web settings is where that happens. */
    NoTemplates,
}

/** The issuing sheet: a member, then a wording, then one button. */
data class IssueState(
    val templates: List<DocumentTemplate> = emptyList(),
    val member: MemberPick? = null,
    val query: String = "",
    val working: Boolean = false,
)

data class DocumentsUiState(
    val loading: Boolean = true,
    val documents: List<IssuedDocument> = emptyList(),
    /** Member id to name, from the mirror. Empty for a member's own list. */
    val names: Map<String, String> = emptyMap(),
    val error: ApiError? = null,
    /** Whether this role may issue — the server refuses it for anyone else. */
    val canIssue: Boolean = false,
    val issue: IssueState? = null,
    val notice: DocumentNotice? = null,
)

/**
 * What the club has issued — everything for the board, one's own otherwise.
 *
 * One screen for both, like the check-in code and the scanner: "my
 * certificates" and "the club's certificates" are the same list seen from two
 * places, and two destinations with the same name in the shelf were not
 * tellable apart. Which endpoint is asked follows the role, because the
 * board's list is a 403 for a member and the member's own is the wrong list for
 * the board.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class DocumentsViewModel @Inject constructor(
    private val repository: DocumentsRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(DocumentsUiState())
    val uiState: StateFlow<DocumentsUiState> = _uiState.asStateFlow()

    /** The picker's list, following what has been typed into the search field. */
    private val query = MutableStateFlow("")

    val pickable: StateFlow<List<MemberPick>> = query
        .flatMapLatest(repository::members)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(STOP_TIMEOUT), emptyList())

    private var board: Boolean? = null

    fun load(board: Boolean) {
        if (this.board == board) return
        this.board = board
        refresh()

        // Only the board list needs names: a member's own documents are all
        // theirs, and putting their own name on every row says nothing.
        if (board) {
            viewModelScope.launch {
                repository.memberNames().collect { names ->
                    _uiState.value = _uiState.value.copy(names = names)
                }
            }
        }
    }

    fun refresh() {
        val board = this.board ?: return
        _uiState.value = _uiState.value.copy(loading = true, error = null, canIssue = board)

        viewModelScope.launch {
            val result = if (board) repository.allDocuments() else repository.myDocuments()
            _uiState.value = when (result) {
                is ApiResult.Success -> _uiState.value.copy(
                    loading = false,
                    documents = result.data,
                    error = null,
                )

                is ApiResult.Failure -> _uiState.value.copy(
                    loading = false,
                    // Not cleared: a refresh that failed should leave the list
                    // that is already on screen where it is.
                    error = result.error,
                )
            }
        }
    }

    /**
     * Opens the sheet, having first asked what may be issued.
     *
     * The wordings are fetched here rather than with the list: a board member
     * opening the screen to read something should not pay for the templates,
     * and a club with none must be told that at the moment it matters — with a
     * sentence about where they are written, not an empty picker.
     */
    fun startIssue() {
        if (_uiState.value.issue != null) return
        viewModelScope.launch {
            when (val result = repository.templates()) {
                is ApiResult.Success -> _uiState.value = if (result.data.isEmpty()) {
                    _uiState.value.copy(notice = DocumentNotice.NoTemplates)
                } else {
                    _uiState.value.copy(issue = IssueState(templates = result.data))
                }

                is ApiResult.Failure ->
                    _uiState.value = _uiState.value.copy(notice = DocumentNotice.Failed)
            }
        }
    }

    fun setQuery(value: String) {
        query.value = value
        _uiState.value.issue?.let { issue ->
            _uiState.value = _uiState.value.copy(issue = issue.copy(query = value))
        }
    }

    fun pickMember(member: MemberPick) {
        _uiState.value.issue?.let { issue ->
            _uiState.value = _uiState.value.copy(issue = issue.copy(member = member))
        }
    }

    /** Back to the member list, for a mis-tap on a club with 300 members. */
    fun clearMember() {
        _uiState.value.issue?.let { issue ->
            _uiState.value = _uiState.value.copy(issue = issue.copy(member = null))
        }
    }

    fun dismissIssue() {
        _uiState.value = _uiState.value.copy(issue = null)
        query.value = ""
    }

    /**
     * Issue, and only then close the sheet.
     *
     * No optimism: a document is the club certifying something, it gets a
     * verification code somebody may look up, and a row that appears before the
     * server has agreed would be a certificate the check page calls fake.
     */
    fun issue(templateId: String) {
        val issue = _uiState.value.issue ?: return
        val member = issue.member ?: return
        if (issue.working) return

        _uiState.value = _uiState.value.copy(issue = issue.copy(working = true))
        viewModelScope.launch {
            when (val result = repository.issue(member.id, templateId)) {
                is ApiResult.Success -> {
                    _uiState.value = _uiState.value.copy(
                        issue = null,
                        // Straight onto the list rather than a refetch: the
                        // server just said what it created, and the list is
                        // newest first.
                        documents = listOf(result.data) + _uiState.value.documents,
                        notice = DocumentNotice.Issued,
                    )
                    query.value = ""
                }

                is ApiResult.Failure -> _uiState.value = _uiState.value.copy(
                    issue = issue.copy(working = false),
                    notice = DocumentNotice.Failed,
                )
            }
        }
    }

    fun onNoticeShown() {
        _uiState.value = _uiState.value.copy(notice = null)
    }

    private companion object {
        const val STOP_TIMEOUT = 5_000L
    }
}

@Composable
fun DocumentsRoute(
    /** Board and above see the club's documents and may issue; a member sees theirs. */
    canAdminister: Boolean,
    actions: @Composable RowScope.() -> Unit = {},
    onOpenDocument: (documentId: String, title: String) -> Unit = { _, _ -> },
    viewModel: DocumentsViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val pickable by viewModel.pickable.collectAsStateWithLifecycle()
    LaunchedEffect(canAdminister) { viewModel.load(canAdminister) }

    state.issue?.let { issue ->
        IssueSheet(
            state = issue,
            members = pickable,
            onQueryChange = viewModel::setQuery,
            onPickMember = viewModel::pickMember,
            onClearMember = viewModel::clearMember,
            onIssue = viewModel::issue,
            onDismiss = viewModel::dismissIssue,
        )
    }

    DocumentsScreen(
        state = state,
        actions = actions,
        onRefresh = viewModel::refresh,
        onIssueClick = viewModel::startIssue,
        onOpenDocument = onOpenDocument,
        onNoticeShown = viewModel::onNoticeShown,
    )
}

@Composable
fun DocumentsScreen(
    state: DocumentsUiState,
    actions: @Composable RowScope.() -> Unit = {},
    onRefresh: () -> Unit = {},
    onIssueClick: () -> Unit = {},
    onOpenDocument: (documentId: String, title: String) -> Unit = { _, _ -> },
    onNoticeShown: () -> Unit = {},
) {
    UnefyListScaffold(
        title = stringResource(R.string.documents_title),
        actions = actions,
        isRefreshing = state.loading && state.documents.isNotEmpty(),
        onRefresh = onRefresh,
        message = state.notice?.let { notice ->
            stringResource(
                when (notice) {
                    DocumentNotice.Issued -> R.string.documents_issued
                    DocumentNotice.Failed -> R.string.documents_failed
                    DocumentNotice.NoTemplates -> R.string.documents_no_templates
                },
            )
        },
        onMessageShown = onNoticeShown,
        floatingActionButton = {
            if (state.canIssue) {
                FloatingActionButton(onClick = onIssueClick) {
                    Icon(
                        painter = painterResource(DesignR.drawable.ic_add),
                        contentDescription = stringResource(R.string.documents_issue),
                    )
                }
            }
        },
    ) {
        when {
            state.documents.isEmpty() && state.error != null -> item("error") {
                UnefyCenteredState(
                    title = stringResource(R.string.documents_error_title),
                    body = stringResource(R.string.documents_error_body),
                    modifier = Modifier.fillParentMaxHeight(UNEFY_STATE_FILL),
                    action = {
                        OutlinedButton(onClick = onRefresh) {
                            Text(stringResource(R.string.documents_retry))
                        }
                    },
                )
            }

            state.documents.isEmpty() && !state.loading -> item("empty") {
                UnefyCenteredState(
                    title = stringResource(R.string.documents_empty_title),
                    body = stringResource(
                        if (state.canIssue) {
                            R.string.documents_empty_body_board
                        } else {
                            R.string.documents_empty_body_member
                        },
                    ),
                    modifier = Modifier.fillParentMaxHeight(UNEFY_STATE_FILL),
                )
            }

            else -> items(state.documents.size, key = { state.documents[it].id }) { index ->
                val document = state.documents[index]
                DocumentRow(
                    document = document,
                    memberName = state.names[document.memberId],
                    onClick = { onOpenDocument(document.id, document.templateName) },
                )
                UnefyRowDivider()
            }
        }
    }
}

@Composable
private fun DocumentRow(
    document: IssuedDocument,
    memberName: String?,
    onClick: () -> Unit,
) {
    val extended = LocalUnefyColors.current

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.sm),
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(text = document.templateName, style = MaterialTheme.typography.bodyLarge)
            Text(
                text = listOfNotNull(memberName, UnefyFormat.date(document.issuedAt))
                    .joinToString(" · "),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        // Only the exception is marked. A "gültig" pill on every row would make
        // the list about validity, when it is about what the club has issued.
        if (document.isRevoked) {
            UnefyPill(
                text = stringResource(R.string.documents_revoked),
                container = MaterialTheme.colorScheme.errorContainer,
                content = MaterialTheme.colorScheme.onErrorContainer,
            )
        } else if (document.signedAt != null) {
            UnefyPill(
                text = stringResource(R.string.documents_signed),
                container = extended.successContainer,
                content = extended.onSuccessContainer,
            )
        }
    }
}

@Preview
@Composable
private fun DocumentsPreview() {
    UnefyTheme {
        DocumentsScreen(
            state = DocumentsUiState(
                loading = false,
                canIssue = true,
                documents = listOf(
                    IssuedDocument(
                        id = "1",
                        memberId = "m1",
                        templateName = "Mitgliedsbescheinigung",
                        title = "Mitgliedsbescheinigung",
                        issuedAt = "2026-08-11T10:00:00Z",
                        revokedAt = null,
                        revokeReason = null,
                        verificationCode = "ABCD-1234",
                        signedAt = null,
                    ),
                    IssuedDocument(
                        id = "2",
                        memberId = "m2",
                        templateName = "Übungsleiterbescheinigung",
                        title = "Übungsleiterbescheinigung",
                        issuedAt = "2026-07-02T10:00:00Z",
                        revokedAt = "2026-07-03T10:00:00Z",
                        revokeReason = "Tippfehler",
                        verificationCode = null,
                        signedAt = null,
                    ),
                ),
                names = mapOf("m1" to "Susanne Bauer", "m2" to "Jonas Weber"),
            ),
        )
    }
}
