package com.unefy.feature.attendance

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.component.UnefySearchField
import com.unefy.core.designsystem.component.UnefyRowDivider
import com.unefy.core.designsystem.theme.UnefySpacing

/**
 * Check members in by hand, without leaving the scanner.
 *
 * A sheet rather than a screen for one reason: the supervisor is mid-queue. The
 * camera stays bound behind it, the chosen session stays chosen, and dismissing
 * puts them back exactly where they were — a separate destination would make
 * "one person has no phone" cost a round trip through navigation.
 *
 * The list marks who is already in the session, so it answers the question a
 * paper list answers — who is still missing — rather than only taking input.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun ManualPickSheet(
    state: ManualPickState,
    onQueryChange: (String) -> Unit,
    onPick: (MemberPick) -> Unit,
    onGuestNameChange: (String) -> Unit,
    onCheckInGuest: () -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = UnefySpacing.screen),
            verticalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
        ) {
            Text(
                text = stringResource(R.string.scanner_manual_title),
                style = MaterialTheme.typography.titleMedium,
            )

            UnefySearchField(
                value = state.query,
                onValueChange = onQueryChange,
                placeholder = stringResource(R.string.scanner_manual_search),
                modifier = Modifier.fillMaxWidth(),
            )

            // Below the search, above the list: a guest is the exception, and
            // putting the exception first would push the common case down.
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                UnefySearchField(
                    value = state.guestName,
                    onValueChange = onGuestNameChange,
                    placeholder = stringResource(R.string.scanner_guest_placeholder),
                    modifier = Modifier.weight(1f),
                )
                TextButton(
                    onClick = onCheckInGuest,
                    enabled = state.guestName.isNotBlank(),
                ) {
                    Text(stringResource(R.string.scanner_guest_action))
                }
            }

            when {
                state.error != null -> Notice(stringResource(R.string.scanner_manual_error))

                state.members.isEmpty() && !state.loading ->
                    Notice(stringResource(R.string.scanner_manual_empty))

                else -> LazyColumn(
                    // Bounded, so the sheet does not grow past the keyboard on a
                    // long list and swallow the search field.
                    modifier = Modifier.heightIn(max = LIST_MAX_HEIGHT),
                ) {
                    items(state.members, key = { it.id }) { member ->
                        MemberRow(
                            member = member,
                            present = member.id in state.checkedIn,
                            pending = state.pending == member.id,
                            onPick = { onPick(member) },
                        )
                        UnefyRowDivider()
                    }
                }
            }
        }
    }
}

@Composable
private fun MemberRow(
    member: MemberPick,
    present: Boolean,
    pending: Boolean,
    onPick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            // Someone already in the session is not tappable: a second attempt
            // can only be refused, and offering it invites the supervisor to
            // wonder whether the first one took.
            .clickable(enabled = !present && !pending, onClick = onPick)
            .padding(vertical = UnefySpacing.sm),
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = member.name,
                style = MaterialTheme.typography.bodyLarge,
                color = if (present) {
                    MaterialTheme.colorScheme.onSurfaceVariant
                } else {
                    MaterialTheme.colorScheme.onSurface
                },
            )
            Text(
                text = member.memberNumber,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        when {
            pending -> CircularProgressIndicator(modifier = Modifier.size(ICON), strokeWidth = 2.dp)
            present -> Icon(
                painter = painterResource(DesignR.drawable.ic_check),
                contentDescription = stringResource(R.string.scanner_manual_present),
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(ICON),
            )
        }
    }
}

@Composable
private fun Notice(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = TextAlign.Center,
        modifier = Modifier
            .fillMaxWidth()
            .padding(UnefySpacing.lg),
    )
}

private val LIST_MAX_HEIGHT = 420.dp
private val ICON = 24.dp
