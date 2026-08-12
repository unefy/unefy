package com.unefy.feature.documents

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.unefy.core.designsystem.component.UnefyRowDivider
import com.unefy.core.designsystem.component.UnefySearchField
import com.unefy.core.designsystem.component.rememberSearchFieldState
import com.unefy.core.designsystem.theme.UnefySpacing

/**
 * Issuing a document: who, then which wording.
 *
 * Two steps in one sheet rather than a screen, and in that order. The member is
 * asked for first because that is the question the board member came with —
 * somebody is standing there needing a certificate — and because it is the one
 * that can go wrong: picking the wrong wording is visible on the document, and
 * picking the wrong member issues a certificate about a stranger with a
 * verification code on it.
 *
 * The member list comes from the mirror, so it works in the clubhouse cellar.
 * The wordings do not: they were fetched when the sheet opened, because a
 * template the club retired last week must not still be offered here.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun IssueSheet(
    state: IssueState,
    members: List<MemberPick>,
    onQueryChange: (String) -> Unit,
    onPickMember: (MemberPick) -> Unit,
    onClearMember: () -> Unit,
    onIssue: (templateId: String) -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
    ) {
        Column(
            modifier = Modifier.padding(
                start = UnefySpacing.screen,
                end = UnefySpacing.screen,
                bottom = UnefySpacing.lg,
            ),
            verticalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
        ) {
            Text(
                text = stringResource(R.string.documents_issue_title),
                style = MaterialTheme.typography.titleMedium,
            )

            if (state.member == null) {
                UnefySearchField(
                    state = rememberSearchFieldState(onQueryChange),
                    placeholder = stringResource(R.string.documents_issue_search),
                    modifier = Modifier.fillMaxWidth(),
                )

                if (members.isEmpty()) {
                    Notice(stringResource(R.string.documents_issue_no_members))
                } else {
                    LazyColumn(modifier = Modifier.heightIn(max = LIST_MAX_HEIGHT)) {
                        items(members, key = { it.id }) { member ->
                            MemberRow(member = member, onPick = { onPickMember(member) })
                            UnefyRowDivider()
                        }
                    }
                }
            } else {
                // The chosen member stays on screen and stays tappable: this is
                // the step where a mis-tap costs a certificate about the wrong
                // person, so undoing it must not mean closing the sheet.
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable(enabled = !state.working, onClick = onClearMember)
                        .padding(vertical = UnefySpacing.sm),
                    horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = state.member.name,
                            style = MaterialTheme.typography.bodyLarge,
                        )
                        Text(
                            text = state.member.memberNumber,
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    TextButton(onClick = onClearMember, enabled = !state.working) {
                        Text(stringResource(R.string.documents_issue_change_member))
                    }
                }

                UnefyRowDivider(startInset = 0.dp)

                Text(
                    text = stringResource(R.string.documents_issue_hint),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                LazyColumn(modifier = Modifier.heightIn(max = LIST_MAX_HEIGHT)) {
                    items(state.templates, key = { it.id }) { template ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable(enabled = !state.working) { onIssue(template.id) }
                                .padding(vertical = UnefySpacing.md),
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = template.name,
                                    style = MaterialTheme.typography.bodyLarge,
                                )
                                Text(
                                    text = template.title,
                                    style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                        UnefyRowDivider()
                    }
                }

                if (state.working) {
                    Notice(stringResource(R.string.documents_issuing))
                }
            }
        }
    }
}

@Composable
private fun MemberRow(member: MemberPick, onPick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onPick)
            .padding(vertical = UnefySpacing.sm),
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(text = member.name, style = MaterialTheme.typography.bodyLarge)
            Text(
                text = member.memberNumber,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
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
