package com.unefy.feature.events

import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import com.unefy.core.designsystem.component.UnefyChoice
import com.unefy.core.designsystem.component.UnefyChoiceField
import com.unefy.core.designsystem.component.UnefyDateTimeField
import com.unefy.core.designsystem.component.UnefyFormSection
import com.unefy.core.designsystem.component.UnefySwitchField
import com.unefy.core.designsystem.component.UnefyTextField

/**
 * An event's editable fields, once — shared by the detail screen and by the one
 * that creates an event. See `MemberFormFields` for why this is not duplicated.
 */
@Composable
fun ColumnScope.EventFormFields(
    draft: EventDraft,
    onChange: ((EventDraft) -> EventDraft) -> Unit,
) {
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
            // Caught here rather than by the server hours later, when the queue
            // finally sends it and nobody remembers typing it.
            error = stringResource(R.string.event_form_ends_before_start)
                .takeIf { draft.endsBeforeItStarts },
        )
        UnefySwitchField(
            label = stringResource(R.string.event_form_all_day),
            checked = draft.allDay,
            onCheckedChange = { v -> onChange { it.copy(allDay = v) } },
        )
    }

    UnefyFormSection(stringResource(R.string.event_form_section_registration)) {
        UnefySwitchField(
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
