package com.unefy.feature.members

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.component.UnefyCenteredState
import com.unefy.core.designsystem.component.UNEFY_STATE_FILL
import com.unefy.core.designsystem.component.UnefyListScaffold
import com.unefy.core.designsystem.component.UnefyLoadMoreFooter
import com.unefy.core.designsystem.component.UnefyRowDivider
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.DirectoryEntry
import com.unefy.core.network.ApiError
import com.unefy.core.network.PageTracker
import com.unefy.core.network.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

// --- Own profile ------------------------------------------------------------

@HiltViewModel
class MyProfileViewModel @Inject constructor(
    private val repository: MembersRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow<MemberDetailUiState>(MemberDetailUiState.Loading)
    val uiState: StateFlow<MemberDetailUiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun load() {
        _uiState.value = MemberDetailUiState.Loading
        viewModelScope.launch {
            _uiState.value = when (val result = repository.me()) {
                is ApiResult.Success -> MemberDetailUiState.Content(result.data)
                is ApiResult.Failure -> MemberDetailUiState.Failure(result.error)
            }
            // After the record rather than beside it: the offices belong to the
            // member this call just resolved, and an account with none — which
            // is most of them — should not hold the screen up for a second call.
            // A failure leaves the section absent; not holding an office and not
            // being able to ask look the same here on purpose.
            val offices = (repository.myFunctions() as? ApiResult.Success)?.data.orEmpty()
            if (offices.isNotEmpty()) {
                _uiState.update { state ->
                    (state as? MemberDetailUiState.Content)?.copy(functions = offices) ?: state
                }
            }
        }
    }
}

/**
 * The signed-in member's own record.
 *
 * A top-level tab, so it wears the same header as every other section — the
 * big title and the account action, not the pushed detail's compact bar. The
 * body below is still [MemberDetailContent]: the difference between "a member"
 * and "me" is which record is loaded, not how it is presented. A 404 is a
 * normal state here — a board account that administers a club it does not
 * belong to has no member record.
 */
@Composable
fun MyProfileRoute(
    actions: @Composable RowScope.() -> Unit = {},
    onOpenConsents: () -> Unit = {},
    viewModel: MyProfileViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    MyProfileScreen(
        state = state,
        actions = actions,
        onRetry = viewModel::load,
        onOpenConsents = onOpenConsents,
    )
}

@Composable
fun MyProfileScreen(
    state: MemberDetailUiState,
    actions: @Composable RowScope.() -> Unit = {},
    onRetry: () -> Unit = {},
    onOpenConsents: () -> Unit = {},
) {
    UnefyListScaffold(
        title = stringResource(R.string.profile_title),
        actions = actions,
    ) {
        when (state) {
            MemberDetailUiState.Loading -> Unit

            is MemberDetailUiState.Failure -> item {
                if (state.error is ApiError.NotFound) {
                    UnefyCenteredState(
                        title = stringResource(R.string.profile_none_title),
                        body = stringResource(R.string.profile_none_body),
                        modifier = Modifier.fillParentMaxHeight(UNEFY_STATE_FILL),
                    )
                } else {
                    UnefyCenteredState(
                        title = stringResource(R.string.error_generic_title),
                        modifier = Modifier.fillParentMaxHeight(UNEFY_STATE_FILL),
                        action = {
                            OutlinedButton(onClick = onRetry) {
                                Text(stringResource(R.string.members_retry))
                            }
                        },
                    )
                }
            }

            is MemberDetailUiState.Content -> {
                item { MemberDetailContent(state.member, functions = state.functions) }
                // Under the record, not in the header: consents are about this
                // member, and the screen they open is a rare and deliberate
                // visit rather than something to reach for every evening.
                item("consents") {
                    TextButton(
                        onClick = onOpenConsents,
                        modifier = Modifier.padding(
                            horizontal = UnefySpacing.sm,
                            vertical = UnefySpacing.md,
                        ),
                    ) { Text(stringResource(R.string.profile_consents)) }
                }
            }
        }
    }
}

// --- Club directory ---------------------------------------------------------

sealed interface DirectoryUiState {
    data object Loading : DirectoryUiState

    data class Content(
        val entries: List<DirectoryEntry>,
        val isRefreshing: Boolean = false,
        /** A refresh that failed, so the screen can say so and then forget it. */
        val refreshFailed: Boolean = false,
        /** A further page is on its way, so the list can show a footer. */
        val isLoadingMore: Boolean = false,
    ) : DirectoryUiState

    data class Failure(val error: ApiError) : DirectoryUiState
}

@HiltViewModel
class DirectoryViewModel @Inject constructor(
    private val repository: MembersRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow<DirectoryUiState>(DirectoryUiState.Loading)
    val uiState: StateFlow<DirectoryUiState> = _uiState.asStateFlow()

    private val pages = PageTracker()

    /** Cancelled by [load], so a late page cannot append to a reloaded list. */
    private var moreInFlight: Job? = null

    init {
        load()
    }

    fun retry() = load()

    fun refresh() = load(refreshing = true)

    fun onMessageShown() = _uiState.update { state ->
        (state as? DirectoryUiState.Content)?.copy(refreshFailed = false) ?: state
    }

    fun loadMore() {
        if (!pages.start()) return
        _uiState.update { state ->
            (state as? DirectoryUiState.Content)?.copy(isLoadingMore = true) ?: state
        }

        moreInFlight = viewModelScope.launch {
            when (val result = repository.directory(page = pages.next)) {
                is ApiResult.Success -> {
                    pages.advance(result.meta)
                    _uiState.update { state ->
                        (state as? DirectoryUiState.Content)?.copy(
                            entries = state.entries + result.data,
                            isLoadingMore = false,
                        ) ?: state
                    }
                }

                is ApiResult.Failure -> {
                    pages.fail()
                    _uiState.update { state ->
                        (state as? DirectoryUiState.Content)
                            ?.copy(isLoadingMore = false, refreshFailed = true) ?: state
                    }
                }
            }
        }
    }

    private fun load(refreshing: Boolean = false) {
        moreInFlight?.cancel()
        val current = _uiState.value
        if (refreshing && current is DirectoryUiState.Content) {
            _uiState.value = current.copy(isRefreshing = true, refreshFailed = false)
        } else {
            _uiState.value = DirectoryUiState.Loading
        }
        pages.reset()

        viewModelScope.launch {
            _uiState.value = when (val result = repository.directory(page = 1)) {
                is ApiResult.Success -> {
                    pages.advance(result.meta)
                    DirectoryUiState.Content(result.data)
                }

                // A refresh that fails keeps the list it already has and says so
                // in a snackbar, rather than trading it for a full-screen error.
                is ApiResult.Failure -> (_uiState.value as? DirectoryUiState.Content)
                    ?.copy(isRefreshing = false, refreshFailed = true)
                    ?: DirectoryUiState.Failure(result.error)
            }
        }
    }
}

@Composable
fun DirectoryRoute(
    actions: @Composable RowScope.() -> Unit = {},
    viewModel: DirectoryViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    DirectoryScreen(
        state = state,
        actions = actions,
        onRetry = viewModel::retry,
        onRefresh = viewModel::refresh,
        onLoadMore = viewModel::loadMore,
        onMessageShown = viewModel::onMessageShown,
    )
}

/**
 * Who else is in the club. Names and category only — the backend will not send
 * more, and this screen is built so there is nothing more to show.
 */
@Composable
fun DirectoryScreen(
    state: DirectoryUiState,
    actions: @Composable RowScope.() -> Unit = {},
    onRetry: () -> Unit = {},
    onRefresh: () -> Unit = {},
    onLoadMore: () -> Unit = {},
    onMessageShown: () -> Unit = {},
) {
    val content = state as? DirectoryUiState.Content

    UnefyListScaffold(
        title = stringResource(R.string.directory_title),
        actions = actions,
        isRefreshing = content?.isRefreshing == true,
        onRefresh = onRefresh,
        onLoadMore = onLoadMore,
        message = stringResource(DesignR.string.refresh_failed)
            .takeIf { content?.refreshFailed == true },
        onMessageShown = onMessageShown,
    ) {
        when (state) {
            DirectoryUiState.Loading -> Unit

            is DirectoryUiState.Failure -> item {
                UnefyCenteredState(
                    title = stringResource(R.string.error_generic_title),
                    modifier = Modifier.fillParentMaxHeight(UNEFY_STATE_FILL),
                    action = {
                        OutlinedButton(onClick = onRetry) {
                            Text(stringResource(R.string.members_retry))
                        }
                    },
                )
            }

            is DirectoryUiState.Content -> {
                items(state.entries, key = { it.id }) { entry ->
                    DirectoryRow(entry)
                    UnefyRowDivider()
                }
                if (state.isLoadingMore) item(key = "more") { UnefyLoadMoreFooter() }
            }
        }
    }
}

@Composable
private fun DirectoryRow(entry: DirectoryEntry) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.md),
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.md),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Surface(
            shape = CircleShape,
            color = MaterialTheme.colorScheme.surfaceContainerHighest,
            modifier = Modifier.size(40.dp),
        ) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(
                    text = entry.initials,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                )
            }
        }
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = entry.displayName,
                style = MaterialTheme.typography.titleMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            entry.category?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Preview
@Composable
private fun DirectoryPreview() {
    UnefyTheme {
        DirectoryScreen(
            state = DirectoryUiState.Content(
                listOf(
                    DirectoryEntry("1", "Susanne", "Bauer", "Erwachsene"),
                    DirectoryEntry("2", "Jonas", "Hoffmann", "Jugend"),
                ),
            ),
        )
    }
}
