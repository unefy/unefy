package com.unefy.feature.events

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.unefy.core.designsystem.component.UnefyChoice
import com.unefy.core.designsystem.component.UnefyChoiceField
import com.unefy.core.designsystem.component.UnefyDateTimeField
import com.unefy.core.designsystem.component.UnefyDetailScaffold
import com.unefy.core.designsystem.component.UnefyFormActions
import com.unefy.core.designsystem.component.UnefyFormSection
import com.unefy.core.designsystem.component.UnefyTextField
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/** Creating an event and editing one. The member form's twin — see its notes. */
data class EventFormUiState(
    val draft: EventDraft = EventDraft(),
    val eventId: String? = null,
    val loading: Boolean = false,
    val saving: Boolean = false,
)

@HiltViewModel
class EventFormViewModel @Inject constructor(
    private val repository: EventsRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(EventFormUiState())
    val uiState: StateFlow<EventFormUiState> = _uiState.asStateFlow()

    private var bound = false

    fun bind(eventId: String?) {
        if (bound) return
        bound = true
        _uiState.value = EventFormUiState(eventId = eventId, loading = eventId != null)
        if (eventId == null) return

        viewModelScope.launch {
            val draft = repository.draftFor(eventId).first()
            _uiState.value = _uiState.value.copy(draft = draft ?: EventDraft(), loading = false)
        }
    }

    fun update(change: (EventDraft) -> EventDraft) {
        _uiState.value = _uiState.value.copy(draft = change(_uiState.value.draft))
    }

    fun save(onSaved: (String) -> Unit) {
        val state = _uiState.value
        if (!state.draft.isComplete || state.saving) return

        _uiState.value = state.copy(saving = true)
        viewModelScope.launch {
            val id = repository.save(state.eventId, state.draft)
            _uiState.value = _uiState.value.copy(saving = false)
            onSaved(id)
        }
    }
}

@Composable
fun EventFormRoute(
    eventId: String? = null,
    onBack: () -> Unit = {},
    onSaved: (String) -> Unit = {},
    viewModel: EventFormViewModel = hiltViewModel(),
) {
    LaunchedEffect(eventId) { viewModel.bind(eventId) }
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
    val creating = state.eventId == null
    val title = stringResource(
        if (creating) R.string.event_form_create_title else R.string.event_form_edit_title,
    )

    UnefyDetailScaffold(collapsedTitle = title, onBack = onBack) {
        Text(
            text = title,
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.padding(
                horizontal = UnefySpacing.screen,
                vertical = UnefySpacing.md,
            ),
        )

        if (state.loading) return@UnefyDetailScaffold

        val draft = state.draft

        UnefyFormSection(stringResource(R.string.event_form_section_what)) {
            UnefyTextField(
                label = stringResource(R.string.event_form_title),
                value = draft.title,
                onValueChange = { v -> onChange { it.copy(title = v) } },
                required = true,
            )
            UnefyChoiceField(
                label = stringResource(R.string.event_form_type),
                options = typeOptions(),
                selectedKey = draft.eventType,
                onSelect = { v -> onChange { it.copy(eventType = v) } },
            )
            UnefyTextField(
                label = stringResource(R.string.event_form_description),
                value = draft.description.orEmpty(),
                onValueChange = { v -> onChange { it.copy(description = v) } },
                singleLine = false,
            )
            UnefyTextField(
                label = stringResource(R.string.event_form_location),
                value = draft.location.orEmpty(),
                onValueChange = { v -> onChange { it.copy(location = v) } },
            )
        }

        UnefyFormSection(stringResource(R.string.event_form_section_when)) {
            UnefyDateTimeField(
                label = stringResource(R.string.event_form_starts_at),
                value = draft.startsAt,
                onValueChange = { v -> onChange { it.copy(startsAt = v) } },
                required = true,
            )
            UnefyDateTimeField(
                label = stringResource(R.string.event_form_ends_at),
                value = draft.endsAt,
                onValueChange = { v -> onChange { it.copy(endsAt = v) } },
                // Caught here rather than by the server hours later, when the
                // queue finally sends it and nobody remembers typing it.
                error = stringResource(R.string.event_form_ends_before_start)
                    .takeIf { draft.endsBeforeItStarts },
            )
            SwitchRow(
                label = stringResource(R.string.event_form_all_day),
                checked = draft.allDay,
                onCheckedChange = { v -> onChange { it.copy(allDay = v) } },
            )
        }

        UnefyFormSection(stringResource(R.string.event_form_section_registration)) {
            SwitchRow(
                label = stringResource(R.string.event_form_registration_required),
                checked = draft.registrationRequired,
                onCheckedChange = { v -> onChange { it.copy(registrationRequired = v) } },
            )
            if (draft.registrationRequired) {
                UnefyTextField(
                    label = stringResource(R.string.event_form_max_participants),
                    value = draft.maxParticipants?.toString().orEmpty(),
                    onValueChange = { v ->
                        // Anything unparseable — including empty — means "no
                        // limit", which is what the server understands by null.
                        onChange { it.copy(maxParticipants = v.toIntOrNull()?.takeIf { n -> n > 0 }) }
                    },
                    keyboardType = KeyboardType.Number,
                )
            }
        }

        UnefyFormActions(
            saveLabel = stringResource(
                if (creating) R.string.event_form_create else R.string.event_form_save,
            ),
            onSave = onSave,
            enabled = draft.isComplete,
            saving = state.saving,
            blockedReason = stringResource(
                if (draft.endsBeforeItStarts) {
                    R.string.event_form_ends_before_start
                } else {
                    R.string.event_form_needs_title_and_start
                },
            ),
        )

        Text(
            text = stringResource(R.string.event_form_queue_hint),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = UnefySpacing.screen)
                .padding(bottom = UnefySpacing.lg),
        )
    }
}

@Composable
private fun SwitchRow(label: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(text = label, style = MaterialTheme.typography.bodyLarge)
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}

/**
 * The types the backend's `EVENT_TYPE_PATTERN` allows, minus `competition`.
 *
 * Competition events carry a session link this form does not collect, and the
 * server forces the type when one is present — offering it here would let
 * somebody create a "competition" that is not attached to one.
 */
@Composable
private fun typeOptions() = listOf(
    UnefyChoice("training", stringResource(R.string.event_type_training)),
    UnefyChoice("meeting", stringResource(R.string.event_type_meeting)),
    UnefyChoice("celebration", stringResource(R.string.event_type_celebration)),
    UnefyChoice("other", stringResource(R.string.event_type_other)),
)

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
