package com.unefy.feature.members

import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.unefy.core.designsystem.component.UnefyDetailScaffold
import com.unefy.core.designsystem.component.UnefySaveBar
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Creating a member.
 *
 * Editing is not here — it happens on the detail screen, in place. This screen
 * exists for the one case that has no detail screen to edit: a record that does
 * not exist yet. It shares its fields with that screen via [MemberFormFields].
 */
data class MemberFormUiState(
    val draft: MemberDraft = MemberDraft(),
    val saving: Boolean = false,
)

@HiltViewModel
class MemberFormViewModel @Inject constructor(
    private val repository: MembersRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(MemberFormUiState())
    val uiState: StateFlow<MemberFormUiState> = _uiState.asStateFlow()

    fun update(change: (MemberDraft) -> MemberDraft) {
        _uiState.value = _uiState.value.copy(draft = change(_uiState.value.draft))
    }

    /**
     * Saves into the queue and hands back the id.
     *
     * Cannot fail, which is why [onSaved] takes no result: the write is on the
     * device the moment this returns, and everything after that is the queue's
     * problem, not this screen's.
     */
    fun save(onSaved: (String) -> Unit) {
        val state = _uiState.value
        if (!state.draft.isComplete || state.saving) return

        _uiState.value = state.copy(saving = true)
        viewModelScope.launch {
            val id = repository.save(null, state.draft)
            _uiState.value = _uiState.value.copy(saving = false)
            onSaved(id)
        }
    }
}

@Composable
fun MemberFormRoute(
    onBack: () -> Unit = {},
    onSaved: (String) -> Unit = {},
    viewModel: MemberFormViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    MemberFormScreen(
        state = state,
        onBack = onBack,
        onChange = viewModel::update,
        onSave = { viewModel.save(onSaved) },
    )
}

@Composable
fun MemberFormScreen(
    state: MemberFormUiState,
    onBack: () -> Unit = {},
    onChange: ((MemberDraft) -> MemberDraft) -> Unit = {},
    onSave: () -> Unit = {},
) {
    val title = stringResource(R.string.member_form_create_title)

    UnefyDetailScaffold(
        collapsedTitle = title,
        onBack = onBack,
        overlay = {
            // Always visible here, unlike on the detail screen: a blank form
            // that has been opened deliberately is already "unsaved", and
            // hiding its only action until a keystroke would read as broken.
            UnefySaveBar(
                visible = true,
                onSave = onSave,
                onDiscard = onBack,
                saving = state.saving,
                saveLabel = stringResource(R.string.member_form_create),
                blockedReason = stringResource(R.string.member_form_needs_names)
                    .takeIf { !state.draft.isComplete },
                modifier = Modifier.align(Alignment.BottomCenter),
            )
        },
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.padding(
                horizontal = UnefySpacing.screen,
                vertical = UnefySpacing.md,
            ),
        )

        MemberFormFields(draft = state.draft, onChange = onChange)

        Text(
            text = stringResource(R.string.member_form_queue_hint),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier
                .fillMaxWidth()
                .padding(UnefySpacing.screen),
        )
        Spacer(modifier = Modifier.height(SAVE_BAR_CLEARANCE))
    }
}

/** Roughly the save bar's height — content must be scrollable past it. */
private val SAVE_BAR_CLEARANCE = 96.dp

@Preview
@Composable
private fun MemberFormPreview() {
    UnefyTheme {
        MemberFormScreen(
            state = MemberFormUiState(
                draft = MemberDraft(firstName = "Ida", lastName = "Beispiel"),
            ),
        )
    }
}
