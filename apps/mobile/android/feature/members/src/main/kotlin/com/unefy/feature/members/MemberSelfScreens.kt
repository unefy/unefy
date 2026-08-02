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
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
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
import com.unefy.core.designsystem.component.UnefyListScaffold
import com.unefy.core.designsystem.component.UnefyRowDivider
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.DirectoryEntry
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
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
        }
    }
}

/**
 * The signed-in member's own record.
 *
 * Reuses the detail screen rather than duplicating it: the difference between
 * "a member" and "me" is which record is loaded, not how it is presented. A 404
 * is a normal state here — a board account that administers a club it does not
 * belong to has no member record.
 */
@Composable
fun MyProfileRoute(
    actions: @Composable RowScope.() -> Unit = {},
    viewModel: MyProfileViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    if (state is MemberDetailUiState.Failure &&
        (state as MemberDetailUiState.Failure).error is ApiError.NotFound
    ) {
        NoMemberRecord(actions = actions)
    } else {
        MemberDetailScreen(
            state = state,
            showBack = false,
            title = stringResource(R.string.profile_title),
            actions = actions,
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun NoMemberRecord(actions: @Composable RowScope.() -> Unit) {
    Scaffold(topBar = { TopAppBar(title = {}, actions = actions) }) { insets ->
        Column(
            modifier = Modifier.fillMaxSize().padding(insets),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            NoMemberRecordBody()
        }
    }
}

@Composable
private fun NoMemberRecordBody() {
    Column(
        modifier = Modifier.padding(UnefySpacing.lg),
        verticalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = stringResource(R.string.profile_none_title),
            style = MaterialTheme.typography.headlineSmall,
        )
        Text(
            text = stringResource(R.string.profile_none_body),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

// --- Club directory ---------------------------------------------------------

sealed interface DirectoryUiState {
    data object Loading : DirectoryUiState
    data class Content(val entries: List<DirectoryEntry>) : DirectoryUiState
    data class Failure(val error: ApiError) : DirectoryUiState
}

@HiltViewModel
class DirectoryViewModel @Inject constructor(
    private val repository: MembersRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow<DirectoryUiState>(DirectoryUiState.Loading)
    val uiState: StateFlow<DirectoryUiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun retry() = load()

    private fun load() {
        _uiState.value = DirectoryUiState.Loading
        viewModelScope.launch {
            _uiState.value = when (val result = repository.directory()) {
                is ApiResult.Success -> DirectoryUiState.Content(result.data)
                is ApiResult.Failure -> DirectoryUiState.Failure(result.error)
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
    DirectoryScreen(state = state, actions = actions, onRetry = viewModel::retry)
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
) {
    UnefyListScaffold(title = stringResource(R.string.directory_title), actions = actions) {
        when (state) {
            DirectoryUiState.Loading -> Unit

            is DirectoryUiState.Failure -> item {
                Column(
                    modifier = Modifier
                        .fillParentMaxHeight(DIRECTORY_FILL)
                        .fillMaxWidth()
                        .padding(UnefySpacing.lg),
                    verticalArrangement = Arrangement.spacedBy(
                        UnefySpacing.sm,
                        Alignment.CenterVertically,
                    ),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(
                        text = stringResource(R.string.error_generic_title),
                        style = MaterialTheme.typography.headlineSmall,
                    )
                    OutlinedButton(onClick = onRetry) {
                        Text(stringResource(R.string.members_retry))
                    }
                }
            }

            is DirectoryUiState.Content -> items(state.entries, key = { it.id }) { entry ->
                DirectoryRow(entry)
                UnefyRowDivider()
            }
        }
    }
}

private const val DIRECTORY_FILL = 0.7f

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
