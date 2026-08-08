package com.unefy.feature.events

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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
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

/** Creating an event. The member form's twin — see its notes. */
data class EventFormUiState(
    val draft: EventDraft = EventDraft(),
    val saving: Boolean = false,
)

@HiltViewModel
class EventFormViewModel @Inject constructor(
    private val repository: EventsRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(EventFormUiState())
    val uiState: StateFlow<EventFormUiState> = _uiState.asStateFlow()

    fun update(change: (EventDraft) -> EventDraft) {
        _uiState.value = _uiState.value.copy(draft = change(_uiState.value.draft))
    }

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
fun EventFormRoute(
    onBack: () -> Unit = {},
    onSaved: (String) -> Unit = {},
    viewModel: EventFormViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    EventFormScreen(
        state = state,
        onBack = onBack,
        onChange = viewModel::update,
        onSave = { viewModel.save(onSaved) },
    )
}

@Composable
fun EventFormScreen(
    state: EventFormUiState,
    onBack: () -> Unit = {},
    onChange: ((EventDraft) -> EventDraft) -> Unit = {},
    onSave: () -> Unit = {},
) {
    val title = stringResource(R.string.event_form_create_title)

    UnefyDetailScaffold(
        collapsedTitle = title,
        onBack = onBack,
        overlay = {
            UnefySaveBar(
                visible = true,
                onSave = onSave,
                onDiscard = onBack,
                saving = state.saving,
                saveLabel = stringResource(R.string.event_form_create),
                blockedReason = when {
                    state.draft.endsBeforeItStarts ->
                        stringResource(R.string.event_form_ends_before_start)
                    !state.draft.isComplete ->
                        stringResource(R.string.event_form_needs_title_and_start)
                    else -> null
                },
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

        EventFormFields(draft = state.draft, onChange = onChange)

        Text(
            text = stringResource(R.string.event_form_queue_hint),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier
                .fillMaxWidth()
                .padding(UnefySpacing.screen),
        )
        Spacer(modifier = Modifier.height(EVENT_SAVE_BAR_CLEARANCE))
    }
}

/** Roughly the save bar's height — content must be scrollable past it. */
internal val EVENT_SAVE_BAR_CLEARANCE = 96.dp

@Preview
@Composable
private fun EventFormPreview() {
    UnefyTheme {
        EventFormScreen(
            state = EventFormUiState(
                draft = EventDraft(title = "Vereinsabend", startsAt = "2026-09-01T17:00:00Z"),
            ),
        )
    }
}
