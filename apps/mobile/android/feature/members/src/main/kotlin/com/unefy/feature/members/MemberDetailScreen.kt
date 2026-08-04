package com.unefy.feature.members

import android.content.Intent
import androidx.core.net.toUri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.unefy.core.designsystem.component.Field
import com.unefy.core.designsystem.component.UnefyDetailScaffold
import com.unefy.core.designsystem.component.UnefyDetailSection
import com.unefy.core.designsystem.component.UnefyPill
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

sealed interface MemberDetailUiState {
    data object Loading : MemberDetailUiState
    data class Content(val member: Member) : MemberDetailUiState
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

    val uiState: StateFlow<MemberDetailUiState> = combine(
        memberId.flatMapLatest { id -> id?.let(repository::byIdStream) ?: flowOf(null) },
        remote,
    ) { mirrored, result ->
        val fetched = (result as? ApiResult.Success)?.data
        val member = mirrored?.copy(iban = fetched?.iban) ?: fetched
        when {
            member != null -> MemberDetailUiState.Content(member)
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

    fun load(id: String) {
        if (memberId.value == id) return
        memberId.value = id
        remote.value = null

        viewModelScope.launch {
            remote.value = repository.byId(id)
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
    viewModel: MemberDetailViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    LaunchedEffect(memberId) { viewModel.load(memberId) }
    MemberDetailScreen(state = state, onBack = onBack)
}

@Composable
fun MemberDetailScreen(
    state: MemberDetailUiState,
    onBack: () -> Unit = {},
) {
    UnefyDetailScaffold(
        // The name lives in the header below and slides up beside the arrow
        // once it scrolls out — never the same word twice on one screen.
        collapsedTitle = (state as? MemberDetailUiState.Content)?.member?.displayName,
        onBack = onBack,
    ) {
        when (state) {
            MemberDetailUiState.Loading -> Unit
            is MemberDetailUiState.Failure -> Text(
                text = stringResource(R.string.error_generic_body),
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(UnefySpacing.screen),
            )

            is MemberDetailUiState.Content -> MemberDetailContent(state.member)
        }
    }
}

@Composable
internal fun MemberDetailContent(member: Member) {
    val context = LocalContext.current

    Header(member)

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

    UnefyDetailSection(stringResource(R.string.detail_section_contact)) {
        Field(stringResource(R.string.detail_email), member.email)
        Field(stringResource(R.string.detail_phone), member.phone)
        Field(stringResource(R.string.detail_mobile), member.mobile)
    }

    UnefyDetailSection(stringResource(R.string.detail_section_address)) {
        Field(stringResource(R.string.detail_street), member.street)
        Field(stringResource(R.string.detail_city), member.postalLine)
    }

    UnefyDetailSection(stringResource(R.string.detail_section_membership)) {
        Field(stringResource(R.string.detail_category), member.category)
        Field(stringResource(R.string.detail_joined), UnefyFormat.date(member.joinedAt), mono = true)
        Field(stringResource(R.string.detail_left), member.leftAt?.let(UnefyFormat::date), mono = true)
        Field(
            label = stringResource(R.string.detail_birthday),
            value = member.birthday?.let(UnefyFormat::date),
            mono = true,
        )
    }

    UnefyDetailSection(stringResource(R.string.detail_section_banking)) {
        Field(stringResource(R.string.detail_iban), member.maskedIban, mono = true)
    }
}

/**
 * Left-aligned, like every list row in the app.
 *
 * A centred portrait header above left-aligned actions and fields reads as two
 * screens stacked; aligning it left removes the seam and takes about 80dp less
 * vertical space, which the fields get back.
 */
@Composable
private fun Header(member: Member) {
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
            Text(text = member.displayName, style = MaterialTheme.typography.headlineSmall)
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
