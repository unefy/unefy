package com.unefy.feature.members

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.unefy.core.designsystem.component.UnefyChoice
import com.unefy.core.designsystem.component.UnefyChoiceField
import com.unefy.core.designsystem.component.UnefyDateField
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

/**
 * Creating a member and editing one, which are the same screen.
 *
 * They differ in three things and nothing else: the title, the word on the
 * button, and whether an id exists yet. Splitting them into two screens would
 * duplicate a dozen fields to express that.
 */
data class MemberFormUiState(
    val draft: MemberDraft = MemberDraft(),
    /** Null while creating. Also decides which word the button carries. */
    val memberId: String? = null,
    /** The form has not been filled from the record yet. */
    val loading: Boolean = false,
    val saving: Boolean = false,
)

@HiltViewModel
class MemberFormViewModel @Inject constructor(
    private val repository: MembersRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(MemberFormUiState())
    val uiState: StateFlow<MemberFormUiState> = _uiState.asStateFlow()

    private var bound = false

    /**
     * Fills the form once.
     *
     * A one-shot read rather than a subscription: a form that kept following
     * the record would overwrite what somebody is typing the moment a sync
     * brought a newer copy. What the server has meanwhile is dealt with when
     * the write is sent, by last-write-wins.
     */
    fun bind(memberId: String?) {
        if (bound) return
        bound = true
        _uiState.value = MemberFormUiState(memberId = memberId, loading = memberId != null)
        if (memberId == null) return

        viewModelScope.launch {
            val draft = repository.draftFor(memberId).first()
            _uiState.value = _uiState.value.copy(
                // Null means the record is neither mirrored nor queued, which
                // on this screen means somebody deep-linked to something that
                // is not on the device. An empty form is the honest answer.
                draft = draft ?: MemberDraft(),
                loading = false,
            )
        }
    }

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
            val id = repository.save(state.memberId, state.draft)
            _uiState.value = _uiState.value.copy(saving = false)
            onSaved(id)
        }
    }
}

@Composable
fun MemberFormRoute(
    memberId: String? = null,
    onBack: () -> Unit = {},
    onSaved: (String) -> Unit = {},
    viewModel: MemberFormViewModel = hiltViewModel(),
) {
    LaunchedEffect(memberId) { viewModel.bind(memberId) }
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
    val creating = state.memberId == null
    val title = stringResource(
        if (creating) R.string.member_form_create_title else R.string.member_form_edit_title,
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

        UnefyFormSection(stringResource(R.string.member_form_section_person)) {
            UnefyTextField(
                label = stringResource(R.string.member_form_first_name),
                value = draft.firstName,
                onValueChange = { v -> onChange { it.copy(firstName = v) } },
                required = true,
            )
            UnefyTextField(
                label = stringResource(R.string.member_form_last_name),
                value = draft.lastName,
                onValueChange = { v -> onChange { it.copy(lastName = v) } },
                required = true,
            )
            UnefyDateField(
                label = stringResource(R.string.member_form_birthday),
                value = draft.birthday,
                onValueChange = { v -> onChange { it.copy(birthday = v) } },
            )
            UnefyChoiceField(
                label = stringResource(R.string.member_form_gender),
                options = genderOptions(),
                selectedKey = draft.gender,
                onSelect = { v -> onChange { it.copy(gender = v) } },
            )
        }

        UnefyFormSection(stringResource(R.string.member_form_section_contact)) {
            UnefyTextField(
                label = stringResource(R.string.member_form_email),
                value = draft.email.orEmpty(),
                onValueChange = { v -> onChange { it.copy(email = v) } },
                keyboardType = KeyboardType.Email,
            )
            UnefyTextField(
                label = stringResource(R.string.member_form_phone),
                value = draft.phone.orEmpty(),
                onValueChange = { v -> onChange { it.copy(phone = v) } },
                keyboardType = KeyboardType.Phone,
            )
            UnefyTextField(
                label = stringResource(R.string.member_form_mobile),
                value = draft.mobile.orEmpty(),
                onValueChange = { v -> onChange { it.copy(mobile = v) } },
                keyboardType = KeyboardType.Phone,
            )
        }

        UnefyFormSection(stringResource(R.string.member_form_section_address)) {
            UnefyTextField(
                label = stringResource(R.string.member_form_street),
                value = draft.street.orEmpty(),
                onValueChange = { v -> onChange { it.copy(street = v) } },
            )
            UnefyTextField(
                label = stringResource(R.string.member_form_zip),
                value = draft.zipCode.orEmpty(),
                onValueChange = { v -> onChange { it.copy(zipCode = v) } },
            )
            UnefyTextField(
                label = stringResource(R.string.member_form_city),
                value = draft.city.orEmpty(),
                onValueChange = { v -> onChange { it.copy(city = v) } },
            )
        }

        UnefyFormSection(stringResource(R.string.member_form_section_membership)) {
            UnefyChoiceField(
                label = stringResource(R.string.member_form_status),
                options = statusOptions(),
                selectedKey = draft.status,
                onSelect = { v -> onChange { it.copy(status = v) } },
            )
            UnefyTextField(
                label = stringResource(R.string.member_form_category),
                value = draft.category.orEmpty(),
                onValueChange = { v -> onChange { it.copy(category = v) } },
            )
            UnefyDateField(
                label = stringResource(R.string.member_form_joined_at),
                value = draft.joinedAt,
                onValueChange = { v -> onChange { it.copy(joinedAt = v) } },
                // Left empty on a creation the server dates today, which is
                // right far more often than any date this form could guess.
            )
        }

        UnefyFormActions(
            saveLabel = stringResource(
                if (creating) R.string.member_form_create else R.string.member_form_save,
            ),
            onSave = onSave,
            enabled = draft.isComplete,
            saving = state.saving,
            blockedReason = stringResource(R.string.member_form_needs_names),
        )

        // Said plainly rather than implied by a spinner: this app saves to the
        // phone first, always, and somebody who has just typed a member in a
        // cellar should be told that is normal and not a failure.
        Text(
            text = stringResource(R.string.member_form_queue_hint),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = UnefySpacing.screen)
                .padding(bottom = UnefySpacing.lg),
        )
    }
}

// The same strings the detail screen shows, deliberately: a value that reads
// "Divers" on one screen and something else on the next looks like two fields.
@Composable
private fun genderOptions() = listOf(
    UnefyChoice("male", stringResource(R.string.gender_male)),
    UnefyChoice("female", stringResource(R.string.gender_female)),
    UnefyChoice("diverse", stringResource(R.string.gender_diverse)),
)

@Composable
private fun statusOptions() = listOf(
    UnefyChoice("active", stringResource(R.string.member_status_active)),
    UnefyChoice("inactive", stringResource(R.string.member_status_inactive)),
    UnefyChoice("pending", stringResource(R.string.member_status_pending)),
    UnefyChoice("resigned", stringResource(R.string.member_status_resigned)),
)

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
