package com.unefy.feature.members

import android.content.Intent
import androidx.core.net.toUri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.TextButton
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.component.Field
import com.unefy.core.designsystem.component.UnefyDetailScaffold
import com.unefy.core.designsystem.component.UnefyDetailSection
import com.unefy.core.designsystem.component.UnefyPill
import com.unefy.core.designsystem.component.UnefySaveBar
import com.unefy.core.designsystem.theme.LocalUnefyColors
import com.unefy.core.designsystem.theme.UnefyFormat
import com.unefy.core.designsystem.theme.UnefyNumericTextStyle
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.Member
import com.unefy.core.model.MemberStatus
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/**
 * Revoking this member's check-in codes — a lost phone, a device passed on.
 *
 * Its own small state rather than a snackbar: this screen has no message
 * channel, and the outcome is worth leaving on screen anyway. A board member
 * who taps it wants to see that it took, not catch a banner on its way past.
 */
enum class RevokeState {
    Idle,
    Working,

    /** Done. Every device holding an old seed is cut off, this member's own too. */
    Done,

    /** The request did not reach the server. Deliberately not queued — see the
     *  repository: a revocation that waits is not a revocation. */
    Failed,
}

sealed interface MemberDetailUiState {
    data object Loading : MemberDetailUiState
    data class Content(
        val member: Member,
        val federations: List<FederationMembership> = emptyList(),
        /**
         * What the fields currently show — the record, with anything typed on
         * top. There is no "edit mode": the screen is always the record, and
         * this is the record as it would be if saved.
         */
        val draft: MemberDraft = member.toDraft(),
        /** Something has been typed that is not the record. Shows the save bar. */
        val dirty: Boolean = false,
        val saving: Boolean = false,
        /** Where the code revocation stands, if it was asked for at all. */
        val revoke: RevokeState = RevokeState.Idle,
    ) : MemberDetailUiState

    data class Failure(val error: ApiError) : MemberDetailUiState
}

/**
 * One member, from two sources that answer different questions.
 *
 * The mirror has everything this screen shows except the bank details, and it has
 * it without a network — so tapping a row is instant, and still works in the
 * basement the list itself was read in. The banking fields are deliberately never
 * written to disk, so they come from the server or not at all.
 *
 * The two are merged rather than raced. Whichever arrives last must not win: the
 * mirror is authoritative for the fields it holds, because a sync can update them
 * while this screen is open, and the fetched copy contributes only the one field
 * the mirror does not carry. Letting either replace the other wholesale means the
 * IBAN appears and then vanishes the next time the row is synced.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class MemberDetailViewModel @Inject constructor(
    private val repository: MembersRepository,
) : ViewModel() {

    private val memberId = MutableStateFlow<String?>(null)

    /** The server's answer, kept only for the fields the mirror leaves out. */
    private val remote = MutableStateFlow<ApiResult<Member>?>(null)

    /**
     * Federation memberships come only from the server — they are not mirrored.
     * A failed fetch (offline, or a plain member's 403) leaves the list empty
     * and the section simply does not render; there is no error state for a
     * section that is optional to begin with.
     */
    private val federations = MutableStateFlow<List<FederationMembership>>(emptyList())

    /**
     * What has been typed, or null while the screen still shows the record
     * untouched.
     *
     * Null rather than "a draft equal to the record" so that a sync arriving
     * while somebody reads the screen updates the fields, and one arriving
     * while somebody *types* does not yank the text out from under them.
     */
    private val draft = MutableStateFlow<MemberDraft?>(null)

    private val saving = MutableStateFlow(false)

    private val revoke = MutableStateFlow(RevokeState.Idle)

    /** Two small flags as one source: `combine` tops out at five of them. */
    private val progress = combine(saving, revoke) { isSaving, revoking -> isSaving to revoking }

    val uiState: StateFlow<MemberDetailUiState> = combine(
        memberId.flatMapLatest { id -> id?.let(repository::byIdStream) ?: flowOf(null) },
        remote,
        federations,
        draft,
        progress,
    ) { mirrored, result, federationList, typed, (isSaving, revoking) ->
        val fetched = (result as? ApiResult.Success)?.data
        val member = mirrored?.copy(iban = fetched?.iban) ?: fetched
        when {
            member != null -> MemberDetailUiState.Content(
                member = member,
                federations = federationList,
                draft = typed ?: member.toDraft(),
                // Compared against the record rather than merely "has been
                // touched": typing a letter and deleting it again should put
                // the bar away, not leave it offering to save nothing.
                dirty = typed != null && typed != member.toDraft(),
                saving = isSaving,
                revoke = revoking,
            )
            // Only a failure when there is nothing to show. Replacing a mirrored
            // member with an error because the connection dropped for a second
            // would be a worse screen than one with an empty IBAN line.
            result is ApiResult.Failure -> MemberDetailUiState.Failure(result.error)
            else -> MemberDetailUiState.Loading
        }
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(SUBSCRIPTION_GRACE_MS),
        initialValue = MemberDetailUiState.Loading,
    )

    /** Type into a field. The first change lifts the draft off the record. */
    fun edit(current: MemberDraft, change: (MemberDraft) -> MemberDraft) {
        draft.value = change(draft.value ?: current)
    }

    /** Back to the record as it stands. */
    fun discard() {
        draft.value = null
    }

    /**
     * Into the queue, then back to showing the record.
     *
     * Clearing the draft afterwards is what makes the mirror take over again —
     * and the mirror already carries the change, because the repository lays
     * unsent writes over it. So the fields do not flicker back to the old
     * values on the way.
     */
    fun save() {
        val id = memberId.value ?: return
        val typed = draft.value ?: return
        if (!typed.isComplete || saving.value) return

        saving.value = true
        viewModelScope.launch {
            repository.save(id, typed)
            draft.value = null
            saving.value = false
        }
    }

    /**
     * Cuts off every check-in code this member's devices can still produce.
     *
     * No optimism and no queue: the screen says "done" only once the server
     * has said so. A revocation that looked successful on the board member's
     * phone while sitting in a queue would be worse than one that plainly
     * failed — the lost phone would keep working and nobody would be looking.
     */
    fun revokeCodes() {
        val id = memberId.value ?: return
        if (revoke.value == RevokeState.Working) return

        revoke.value = RevokeState.Working
        viewModelScope.launch {
            revoke.value = when (repository.revokeAttendanceCodes(id)) {
                is ApiResult.Success -> RevokeState.Done
                is ApiResult.Failure -> RevokeState.Failed
            }
        }
    }

    fun load(id: String) {
        if (memberId.value == id) return
        memberId.value = id
        remote.value = null
        federations.value = emptyList()
        // A different member: whatever was typed belonged to the previous one.
        draft.value = null

        viewModelScope.launch {
            remote.value = repository.byId(id)
        }
        viewModelScope.launch {
            federations.value =
                (repository.federations(id) as? ApiResult.Success)?.data.orEmpty()
        }
    }

    private companion object {
        const val SUBSCRIPTION_GRACE_MS = 5_000L
    }
}

@Composable
fun MemberDetailRoute(
    memberId: String,
    onBack: () -> Unit,
    /** Whether this role may change the record. Read-only rows otherwise. */
    canEdit: Boolean = false,
    viewModel: MemberDetailViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    LaunchedEffect(memberId) { viewModel.load(memberId) }
    MemberDetailScreen(
        state = state,
        onBack = onBack,
        canEdit = canEdit,
        onChange = { change ->
            (state as? MemberDetailUiState.Content)?.let { viewModel.edit(it.draft, change) }
        },
        onSave = viewModel::save,
        onDiscard = viewModel::discard,
        onRevokeCodes = viewModel::revokeCodes,
    )
}

/**
 * A member, and the same screen for changing one.
 *
 * There is no edit mode and no pencil. For a role that may edit, the fields are
 * simply editable where they stand; a save bar appears at the foot as soon as
 * something differs from the record. That is the pattern Linear and the Vercel
 * dashboards use, and it is the one the design system asks for — the read-only
 * rows and the editable ones share their geometry exactly, so the record does
 * not change shape when somebody touches it.
 *
 * Saving per keystroke, the Notion reading of the same idea, is deliberately
 * not what happens: these are a club's records, and a mistyped surname would be
 * in the sync queue before the finger left the key.
 */
@Composable
fun MemberDetailScreen(
    state: MemberDetailUiState,
    onBack: () -> Unit = {},
    canEdit: Boolean = false,
    onChange: ((MemberDraft) -> MemberDraft) -> Unit = {},
    onSave: () -> Unit = {},
    onDiscard: () -> Unit = {},
    onRevokeCodes: () -> Unit = {},
) {
    val content = state as? MemberDetailUiState.Content

    UnefyDetailScaffold(
        // The name lives in the header below and slides up beside the arrow
        // once it scrolls out — never the same word twice on one screen.
        collapsedTitle = content?.member?.displayName,
        onBack = onBack,
        overlay = {
            UnefySaveBar(
                visible = canEdit && content?.dirty == true,
                onSave = onSave,
                onDiscard = onDiscard,
                saving = content?.saving == true,
                blockedReason = stringResource(R.string.member_form_needs_names)
                    .takeIf { content?.draft?.isComplete == false },
                modifier = Modifier.align(Alignment.BottomCenter),
            )
        },
    ) {
        when (state) {
            MemberDetailUiState.Loading -> Unit
            is MemberDetailUiState.Failure -> Text(
                text = stringResource(R.string.error_generic_body),
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(UnefySpacing.screen),
            )

            is MemberDetailUiState.Content -> {
                if (canEdit) {
                    MemberEditableContent(state, onChange)
                } else {
                    MemberDetailContent(state.member, state.federations)
                }
                // Board only: it takes a credential away from somebody, and the
                // server refuses it for anyone else anyway.
                if (canEdit) RevokeCodesSection(state.revoke, onRevokeCodes)
            }
        }
    }
}

/**
 * The record with its fields live.
 *
 * The header and the call/write buttons stay as they are — they are about the
 * member, not about the form — and everything below them becomes the shared
 * field list. Federations are shown read-only underneath: they are not mirrored
 * and nothing on mobile edits them.
 */
@Composable
private fun ColumnScope.MemberEditableContent(
    state: MemberDetailUiState.Content,
    onChange: ((MemberDraft) -> MemberDraft) -> Unit,
) {
    // The header follows what is being typed: renaming somebody and watching
    // the title stay on the old name reads as an edit that did not take.
    Header(state.member, displayName = state.draft.displayName)
    ContactActions(state.member)

    MemberFormFields(draft = state.draft, onChange = onChange)

    ReadOnlyTail(state.member, state.federations)

    // Clears the save bar, which floats over the foot of the content.
    Spacer(modifier = Modifier.height(SAVE_BAR_CLEARANCE))
}

/** Dial and write, which are about the member rather than about the form. */
@Composable
private fun ContactActions(member: Member) {
    val context = LocalContext.current
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = UnefySpacing.screen),
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
    ) {
        member.phone?.let { number ->
            OutlinedButton(
                onClick = {
                    context.startActivity(Intent(Intent.ACTION_DIAL, "tel:$number".toUri()))
                },
            ) { Text(stringResource(R.string.detail_call)) }
        }
        member.email?.let { address ->
            OutlinedButton(
                onClick = {
                    context.startActivity(Intent(Intent.ACTION_SENDTO, "mailto:$address".toUri()))
                },
            ) { Text(stringResource(R.string.detail_write)) }
        }
    }
}

/**
 * Federations and banking, which stay read-only even while editing.
 *
 * Neither is mirrored and neither is editable on mobile — federations have
 * their own screens on the web, and bank details are never written to this
 * device at all.
 */
@Composable
private fun ReadOnlyTail(member: Member, federations: List<FederationMembership>) {
    UnefyDetailSection(
        title = stringResource(R.string.detail_section_federations),
        fields = federations.map { federation ->
            Field(
                label = federation.federation,
                value = listOfNotNull(
                    federation.federationNumber,
                    federation.joinedAt?.let {
                        stringResource(R.string.federation_since, UnefyFormat.date(it))
                    },
                ).joinToString(" · ").ifBlank { null },
                mono = true,
            )
        },
    )

    UnefyDetailSection(
        title = stringResource(R.string.detail_section_banking),
        fields = listOf(
            Field(stringResource(R.string.detail_iban), member.maskedIban, mono = true),
        ),
    )
}

/** Roughly the save bar's height — content must be scrollable past it. */
private val SAVE_BAR_CLEARANCE = 96.dp

@Composable
internal fun MemberDetailContent(
    member: Member,
    federations: List<FederationMembership> = emptyList(),
) {
    Header(member)
    ContactActions(member)

    UnefyDetailSection(
        title = stringResource(R.string.detail_section_contact),
        fields = listOf(
            Field(stringResource(R.string.detail_email), member.email),
            Field(stringResource(R.string.detail_phone), member.phone),
            Field(stringResource(R.string.detail_mobile), member.mobile),
        ),
    )

    UnefyDetailSection(
        title = stringResource(R.string.detail_section_address),
        fields = listOf(
            Field(stringResource(R.string.detail_street), member.street),
            Field(stringResource(R.string.detail_city), member.postalLine),
        ),
    )

    UnefyDetailSection(
        title = stringResource(R.string.detail_section_membership),
        fields = listOf(
            Field(stringResource(R.string.detail_category), member.category),
            Field(
                label = stringResource(R.string.detail_joined),
                value = UnefyFormat.date(member.joinedAt),
                mono = true,
            ),
            Field(
                label = stringResource(R.string.detail_left),
                value = member.leftAt?.let(UnefyFormat::date),
                mono = true,
            ),
            Field(
                label = stringResource(R.string.detail_birthday),
                value = member.birthday?.let(UnefyFormat::date),
                mono = true,
            ),
            Field(stringResource(R.string.detail_gender), member.gender?.let { genderLabel(it) }),
        ),
    )

    ReadOnlyTail(member, federations)
}

/**
 * Left-aligned, like every list row in the app.
 *
 * A centred portrait header above left-aligned actions and fields reads as two
 * screens stacked; aligning it left removes the seam and takes about 80dp less
 * vertical space, which the fields get back.
 */
@Composable
private fun Header(member: Member, displayName: String = member.displayName) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(
                start = UnefySpacing.screen,
                end = UnefySpacing.screen,
                top = UnefySpacing.sm,
                bottom = UnefySpacing.md,
            ),
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.md),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Surface(
            shape = CircleShape,
            color = MaterialTheme.colorScheme.surfaceContainerHighest,
            modifier = Modifier.size(HEADER_AVATAR),
        ) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(
                    text = member.initials,
                    style = MaterialTheme.typography.headlineSmall,
                    color = MaterialTheme.colorScheme.onSurface,
                )
            }
        }

        Column(verticalArrangement = Arrangement.spacedBy(UnefySpacing.xs)) {
            Text(text = displayName, style = MaterialTheme.typography.headlineSmall)
            Row(
                horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = member.memberNumber,
                    style = UnefyNumericTextStyle,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                StatusPill(member.status)
            }
        }
    }
}

@Composable
private fun StatusPill(status: MemberStatus) {
    val extended = LocalUnefyColors.current
    val (label, container, content) = when (status) {
        MemberStatus.ACTIVE -> Triple(
            R.string.member_status_active,
            extended.successContainer,
            extended.onSuccessContainer,
        )
        MemberStatus.PENDING -> Triple(
            R.string.member_status_pending,
            extended.warningContainer,
            extended.onWarningContainer,
        )
        MemberStatus.RESIGNED -> Triple(
            R.string.member_status_resigned,
            MaterialTheme.colorScheme.errorContainer,
            MaterialTheme.colorScheme.onErrorContainer,
        )
        MemberStatus.INACTIVE, MemberStatus.UNKNOWN -> Triple(
            if (status == MemberStatus.INACTIVE) {
                R.string.member_status_inactive
            } else {
                R.string.member_status_unknown
            },
            MaterialTheme.colorScheme.surfaceContainerHighest,
            MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
    UnefyPill(text = stringResource(label), container = container, content = content)
}

/**
 * The backend stores gender as a free string; the three known values get their
 * translation, anything future is shown as-is rather than dropped.
 */
@Composable
private fun genderLabel(gender: String): String = when (gender) {
    "male" -> stringResource(R.string.gender_male)
    "female" -> stringResource(R.string.gender_female)
    "diverse" -> stringResource(R.string.gender_diverse)
    else -> gender
}

private val HEADER_AVATAR = 64.dp

@Preview
@Composable
private fun MemberDetailPreview() {
    UnefyTheme {
        MemberDetailScreen(
            state = MemberDetailUiState.Content(
                Member(
                    id = "1",
                    memberNumber = "TV-012",
                    firstName = "Susanne",
                    lastName = "Bauer",
                    email = "s.bauer@example.org",
                    phone = "+49 170 1234567",
                    mobile = null,
                    birthday = "1981-06-14",
                    gender = "female",
                    street = "Ringstraße 12",
                    zipCode = "72074",
                    city = "Tübingen",
                    status = MemberStatus.ACTIVE,
                    category = "Erwachsene",
                    joinedAt = "2007-04-10",
                    leftAt = null,
                    iban = "DE02120300000000202051",
                ),
            ),
        )
    }
}


/**
 * Taking a member's check-in codes away.
 *
 * At the foot of the record and behind a confirmation, because it is rare,
 * deliberate and cannot be undone from here — the member's own device is cut
 * off along with the lost one and has to fetch a fresh seed. Not styled as a
 * danger zone: nothing is destroyed, and the member is one app open away from
 * a working code again.
 */
@Composable
private fun RevokeCodesSection(state: RevokeState, onRevoke: () -> Unit) {
    var confirming by rememberSaveable { mutableStateOf(false) }

    if (confirming) {
        AlertDialog(
            onDismissRequest = { confirming = false },
            title = { Text(stringResource(R.string.revoke_codes_title)) },
            text = { Text(stringResource(R.string.revoke_codes_message)) },
            confirmButton = {
                TextButton(
                    onClick = {
                        confirming = false
                        onRevoke()
                    },
                ) { Text(stringResource(R.string.revoke_codes_confirm)) }
            },
            dismissButton = {
                TextButton(onClick = { confirming = false }) {
                    Text(stringResource(R.string.revoke_codes_cancel))
                }
            },
        )
    }

    Column(
        modifier = Modifier.padding(
            start = UnefySpacing.screen,
            end = UnefySpacing.screen,
            top = UnefySpacing.lg,
            bottom = UnefySpacing.lg,
        ),
        verticalArrangement = Arrangement.spacedBy(UnefySpacing.xs),
    ) {
        TextButton(
            onClick = { confirming = true },
            enabled = state != RevokeState.Working,
        ) { Text(stringResource(R.string.revoke_codes_action)) }

        when (state) {
            RevokeState.Idle -> Unit
            RevokeState.Working -> Text(
                text = stringResource(R.string.revoke_codes_working),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            RevokeState.Done -> Text(
                text = stringResource(R.string.revoke_codes_done),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            // Said plainly rather than retried quietly: nothing was queued, so
            // the old codes are still working.
            RevokeState.Failed -> Text(
                text = stringResource(R.string.revoke_codes_failed),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
            )
        }
    }
}
