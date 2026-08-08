package com.unefy.feature.members

import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import com.unefy.core.designsystem.component.UnefyChoice
import com.unefy.core.designsystem.component.UnefyChoiceField
import com.unefy.core.designsystem.component.UnefyDateField
import com.unefy.core.designsystem.component.UnefyFormSection
import com.unefy.core.designsystem.component.UnefyTextField

/**
 * A member's editable fields, once.
 *
 * Shared by the detail screen — where editing now happens in place — and by the
 * screen that creates one. Two copies of this list is how a field ends up
 * editable on one screen and absent on the other, which is the bug this file
 * exists to prevent rather than the abstraction it exists to provide.
 *
 * Bank details are not here, deliberately: the mirror does not hold them, so a
 * form offering them would have to fetch them, keep them in memory and send
 * them back. They stay with the web app.
 */
@Composable
fun ColumnScope.MemberFormFields(
    draft: MemberDraft,
    onChange: ((MemberDraft) -> MemberDraft) -> Unit,
) {
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
        )
    }
}

// The same strings the read-only rows show, deliberately: a value that reads
// "Divers" before a tap and something else after looks like two fields.
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
