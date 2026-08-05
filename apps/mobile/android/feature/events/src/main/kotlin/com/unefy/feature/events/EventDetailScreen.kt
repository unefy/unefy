package com.unefy.feature.events

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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import java.time.Instant
import java.time.ZoneId
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.component.Field
import com.unefy.core.designsystem.component.LocalGlassBarHeight
import com.unefy.core.designsystem.component.UnefyDetailScaffold
import com.unefy.core.designsystem.component.UnefyDetailSection
import com.unefy.core.designsystem.component.UnefyPill
import com.unefy.core.designsystem.component.UnefyRowDivider
import com.unefy.core.designsystem.component.UnefySearchField
import com.unefy.core.designsystem.component.rememberSearchFieldState
import com.unefy.core.designsystem.theme.LocalUnefyColors
import com.unefy.core.designsystem.theme.UnefyFormat
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.ClubRole
import com.unefy.core.model.Event
import com.unefy.core.model.EventRegistration

@Composable
fun EventDetailRoute(
    eventId: String,
    role: ClubRole,
    onBack: () -> Unit,
    onOpenAttendanceList: (sessionId: String, sessionTitle: String) -> Unit = { _, _ -> },
    onOpenScanner: () -> Unit = {},
    viewModel: EventDetailViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val picker by viewModel.picker.collectAsStateWithLifecycle()
    LaunchedEffect(eventId) { viewModel.load(eventId) }

    // Starting attendance ends in the scanner: the person who opened the
    // evening is about to check people in, not to read an empty list.
    val started by viewModel.startedSession.collectAsStateWithLifecycle()
    LaunchedEffect(started) {
        if (started != null) {
            viewModel.consumeStartedSession()
            onOpenScanner()
        }
    }

    EventDetailScreen(
        state = state,
        canManage = role.canAdminister,
        picker = picker,
        onBack = onBack,
        onOpenAttendanceList = onOpenAttendanceList,
        onStartAttendance = viewModel::startAttendance,
        onToggleRegistration = viewModel::toggleRegistration,
        onOpenPicker = viewModel::openPicker,
        onDismissPicker = viewModel::dismissPicker,
        onPickerQueryChange = viewModel::setPickerQuery,
        onPickMember = viewModel::pickMember,
        onRemoveRegistration = viewModel::removeRegistration,
        onActionFailedShown = viewModel::onActionFailedShown,
    )
}

@Composable
fun EventDetailScreen(
    state: EventDetailUiState,
    canManage: Boolean = false,
    picker: MemberPickerState = MemberPickerState(),
    onBack: () -> Unit = {},
    onToggleRegistration: () -> Unit = {},
    onOpenPicker: () -> Unit = {},
    onDismissPicker: () -> Unit = {},
    onPickerQueryChange: (String) -> Unit = {},
    onPickMember: (MemberOption) -> Unit = {},
    onRemoveRegistration: (String) -> Unit = {},
    onActionFailedShown: () -> Unit = {},
    onOpenAttendanceList: (sessionId: String, sessionTitle: String) -> Unit = { _, _ -> },
    onStartAttendance: () -> Unit = {},
) {
    val content = state as? EventDetailUiState.Content

    val snackbarHostState = remember { SnackbarHostState() }
    val actionFailedText = stringResource(R.string.event_detail_action_failed)
    LaunchedEffect(content?.actionFailed) {
        if (content?.actionFailed == true) {
            snackbarHostState.showSnackbar(actionFailedText)
            onActionFailedShown()
        }
    }

    if (picker.visible) {
        MemberPickerSheet(
            state = picker,
            registeredMemberIds = content?.registrations.orEmpty().map { it.memberId }.toSet(),
            onQueryChange = onPickerQueryChange,
            onPick = onPickMember,
            onDismiss = onDismissPicker,
        )
    }

    UnefyDetailScaffold(
        collapsedTitle = content?.event?.title,
        onBack = onBack,
        overlay = {
            SnackbarHost(
                hostState = snackbarHostState,
                // Above the floating glass bar, not behind it.
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = LocalGlassBarHeight.current),
            )
        },
    ) {
        when (state) {
            EventDetailUiState.Loading -> Unit
            is EventDetailUiState.Failure -> Text(
                text = stringResource(R.string.event_detail_error_body),
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(UnefySpacing.screen),
            )

            is EventDetailUiState.Content -> EventDetailContent(
                state = state,
                canManage = canManage,
                onToggleRegistration = onToggleRegistration,
                onOpenPicker = onOpenPicker,
                onRemoveRegistration = onRemoveRegistration,
                onOpenAttendanceList = onOpenAttendanceList,
                onStartAttendance = onStartAttendance,
            )
        }
    }
}

@Composable
private fun EventDetailContent(
    state: EventDetailUiState.Content,
    canManage: Boolean,
    onToggleRegistration: () -> Unit,
    onOpenPicker: () -> Unit,
    onRemoveRegistration: (String) -> Unit,
    onOpenAttendanceList: (sessionId: String, sessionTitle: String) -> Unit = { _, _ -> },
    onStartAttendance: () -> Unit = {},
) {
    val event = state.event

    Header(event)

    if (event.registrationRequired) {
        RegistrationBlock(state, onToggleRegistration)
    }

    // Body text, not a label/value field: a description is prose, and prose
    // squeezed into the field pattern reads like a form.
    event.description?.takeIf { it.isNotBlank() }?.let { description ->
        SectionTitle(stringResource(R.string.event_detail_section_description))
        Text(
            text = description,
            style = MaterialTheme.typography.bodyLarge,
            modifier = Modifier.padding(
                horizontal = UnefySpacing.screen,
                vertical = UnefySpacing.sm,
            ),
        )
    }

    UnefyDetailSection(
        title = stringResource(R.string.event_detail_section_details),
        fields = listOf(
            Field(stringResource(R.string.event_detail_location), event.location),
            Field(
                label = stringResource(R.string.event_detail_starts),
                value = if (event.allDay) {
                    UnefyFormat.date(event.startsAt)
                } else {
                    UnefyFormat.dateTime(event.startsAt)
                },
                mono = true,
            ),
            Field(
                label = stringResource(R.string.event_detail_ends),
                value = event.endsAt?.let {
                    if (event.allDay) UnefyFormat.date(it) else UnefyFormat.dateTime(it)
                },
                mono = true,
            ),
            Field(
                label = stringResource(R.string.event_detail_deadline),
                value = event.registrationDeadline?.let(UnefyFormat::dateTime),
                mono = true,
            ),
            Field(stringResource(R.string.event_detail_competition), event.competitionName),
        ),
    )

    // Attendance lives here too, but only for the board: the calendar is the
    // place people look for the evening, and the evening's list should be one
    // tap away — not hidden behind the scanner. Members never see this; the
    // backend sends them an empty array, and attendance is the board's record.
    if (canManage && state.detailLoaded) {
        AttendanceBlock(
            state = state,
            onOpenAttendanceList = onOpenAttendanceList,
            onStartAttendance = onStartAttendance,
        )
    }

    // The board sees the section even when it is empty — it hosts the add
    // button, and an empty list is exactly when adding people starts.
    if (state.detailLoaded && (state.registrations.isNotEmpty() || canManage)) {
        var confirmRemove by remember { mutableStateOf<EventRegistration?>(null) }

        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier
                .fillMaxWidth()
                .padding(start = UnefySpacing.screen, top = UnefySpacing.lg),
        ) {
            Text(
                text = stringResource(
                    R.string.event_detail_section_participants,
                    state.registrations.size,
                ),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.weight(1f),
            )
            if (canManage) {
                TextButton(
                    onClick = onOpenPicker,
                    enabled = state.online,
                    modifier = Modifier.padding(end = UnefySpacing.sm),
                ) { Text(stringResource(R.string.event_detail_add_member)) }
            }
        }

        state.registrations.forEach { registration ->
            ParticipantRow(
                registration = registration,
                canManage = canManage,
                removing = registration.id in state.removing,
                online = state.online,
                onRemove = { confirmRemove = registration },
            )
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        }

        confirmRemove?.let { registration ->
            AlertDialog(
                onDismissRequest = { confirmRemove = null },
                title = { Text(stringResource(R.string.event_detail_remove_title)) },
                text = {
                    Text(
                        stringResource(
                            R.string.event_detail_remove_body,
                            registration.memberName
                                ?: stringResource(R.string.event_detail_participant_unknown),
                        ),
                    )
                },
                confirmButton = {
                    TextButton(
                        onClick = {
                            onRemoveRegistration(registration.id)
                            confirmRemove = null
                        },
                    ) { Text(stringResource(R.string.event_detail_remove_confirm)) }
                },
                dismissButton = {
                    TextButton(onClick = { confirmRemove = null }) {
                        Text(stringResource(R.string.event_detail_remove_cancel))
                    }
                },
            )
        }
    }
}

/**
 * The event's attendance sessions and the way in.
 *
 * A row per session opens the attendance list; with no open session there is
 * one button that starts the evening — prefilled from the event, ending in the
 * scanner, because whoever starts it is about to check people in.
 */
@Composable
private fun AttendanceBlock(
    state: EventDetailUiState.Content,
    onOpenAttendanceList: (sessionId: String, sessionTitle: String) -> Unit,
    onStartAttendance: () -> Unit,
) {
    SectionTitle(stringResource(R.string.event_detail_section_attendance))

    state.attendanceSessions.forEach { session ->
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { onOpenAttendanceList(session.id, session.title) }
                .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.sm),
            horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = stringResource(
                        R.string.event_detail_attendance_row,
                        session.recordCount,
                    ),
                    style = MaterialTheme.typography.bodyLarge,
                )
                Text(
                    text = if (session.status == "closed") {
                        stringResource(R.string.event_detail_attendance_closed)
                    } else {
                        stringResource(R.string.event_detail_attendance_open)
                    },
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        UnefyRowDivider()
    }

    if (state.attendanceSessions.none { it.status == "open" }) {
        TextButton(
            onClick = onStartAttendance,
            enabled = state.online && !state.startingAttendance,
            modifier = Modifier.padding(horizontal = UnefySpacing.sm),
        ) {
            Text(
                stringResource(
                    if (state.startingAttendance) {
                        R.string.event_detail_attendance_starting
                    } else {
                        R.string.event_detail_attendance_start
                    },
                ),
            )
        }
    }
}

/**
 * The board's add sheet, after the attendance pick list: search over the
 * member mirror, rows already on the event marked and not tappable — a second
 * registration can only 409.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MemberPickerSheet(
    state: MemberPickerState,
    registeredMemberIds: Set<String>,
    onQueryChange: (String) -> Unit,
    onPick: (MemberOption) -> Unit,
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
                text = stringResource(R.string.event_detail_add_title),
                style = MaterialTheme.typography.titleMedium,
            )

            UnefySearchField(
                state = rememberSearchFieldState(onQueryChange),
                placeholder = stringResource(R.string.event_detail_add_search),
                modifier = Modifier.fillMaxWidth(),
            )

            when {
                state.failed -> SheetNotice(stringResource(R.string.event_detail_add_error))

                state.options.isEmpty() && !state.loading ->
                    SheetNotice(stringResource(R.string.event_detail_add_empty))

                else -> LazyColumn(
                    // Bounded, so the sheet does not grow past the keyboard on
                    // a long list and swallow the search field.
                    modifier = Modifier
                        .heightIn(max = PICKER_MAX_HEIGHT)
                        .padding(bottom = UnefySpacing.lg),
                ) {
                    items(state.options, key = { it.id }) { option ->
                        PickerRow(
                            option = option,
                            registered = option.id in registeredMemberIds,
                            pending = state.pendingMemberId == option.id,
                            onPick = { onPick(option) },
                        )
                        UnefyRowDivider()
                    }
                }
            }
        }
    }
}

@Composable
private fun PickerRow(
    option: MemberOption,
    registered: Boolean,
    pending: Boolean,
    onPick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(enabled = !registered && !pending, onClick = onPick)
            .padding(vertical = UnefySpacing.sm),
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = option.name,
                style = MaterialTheme.typography.bodyLarge,
                color = if (registered) {
                    MaterialTheme.colorScheme.onSurfaceVariant
                } else {
                    MaterialTheme.colorScheme.onSurface
                },
            )
            Text(
                text = option.memberNumber,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        when {
            pending -> CircularProgressIndicator(
                modifier = Modifier.size(PICKER_ICON),
                strokeWidth = 2.dp,
            )

            registered -> Icon(
                painter = painterResource(DesignR.drawable.ic_check),
                contentDescription = stringResource(R.string.event_detail_add_registered),
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(PICKER_ICON),
            )
        }
    }
}

@Composable
private fun SheetNotice(text: String) {
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

private val PICKER_MAX_HEIGHT = 420.dp
private val PICKER_ICON = 24.dp

@Composable
private fun Header(event: Event) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(
                start = UnefySpacing.screen,
                end = UnefySpacing.screen,
                top = UnefySpacing.sm,
                bottom = UnefySpacing.md,
            ),
        verticalArrangement = Arrangement.spacedBy(UnefySpacing.xs),
    ) {
        Text(
            text = eventTimeRange(event),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(text = event.title, style = MaterialTheme.typography.headlineSmall)

        val typeLabel = eventTypeLabel(event.type)
        val cancelled = event.status == "cancelled"
        if (typeLabel != null || cancelled) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (cancelled) {
                    UnefyPill(
                        text = stringResource(R.string.event_detail_cancelled),
                        container = MaterialTheme.colorScheme.errorContainer,
                        content = MaterialTheme.colorScheme.onErrorContainer,
                    )
                }
                typeLabel?.let {
                    UnefyPill(
                        text = it,
                        container = MaterialTheme.colorScheme.surfaceContainerHighest,
                        content = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

/**
 * The capacity pill and the sign-up control, mirroring the list row's rules:
 * both exist only once the online detail has answered, cancelling stays
 * possible past the deadline, and a closed sign-up says so instead of offering
 * a button that is certain to 409.
 */
@Composable
private fun RegistrationBlock(
    state: EventDetailUiState.Content,
    onToggleRegistration: () -> Unit,
) {
    val event = state.event

    if (!state.detailLoaded) {
        Text(
            text = stringResource(R.string.event_detail_offline_hint),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(
                horizontal = UnefySpacing.screen,
                vertical = UnefySpacing.sm,
            ),
        )
        return
    }

    val extended = LocalUnefyColors.current
    Row(
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.padding(
            horizontal = UnefySpacing.screen,
            vertical = UnefySpacing.sm,
        ),
    ) {
        UnefyPill(
            text = event.maxParticipants
                ?.let {
                    stringResource(R.string.events_registered_of, event.registeredCount, it)
                }
                ?: stringResource(R.string.events_registered, event.registeredCount),
            container = if (event.isFull) {
                extended.warningContainer
            } else {
                MaterialTheme.colorScheme.surfaceContainerHighest
            },
            content = if (event.isFull) {
                extended.onWarningContainer
            } else {
                MaterialTheme.colorScheme.onSurfaceVariant
            },
        )

        val canAct = state.online && !state.busy
        when {
            event.isRegistered -> OutlinedButton(
                onClick = onToggleRegistration,
                enabled = canAct,
            ) { Text(stringResource(R.string.events_unregister)) }

            event.registrationOpen(state.now) -> Button(
                onClick = onToggleRegistration,
                enabled = canAct,
            ) { Text(stringResource(R.string.events_register)) }

            else -> Text(
                text = stringResource(R.string.events_registration_closed),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun ParticipantRow(
    registration: EventRegistration,
    canManage: Boolean = false,
    removing: Boolean = false,
    online: Boolean = false,
    onRemove: () -> Unit = {},
) {
    val extended = LocalUnefyColors.current
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.sm),
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = registration.memberName
                ?: stringResource(R.string.event_detail_participant_unknown),
            style = MaterialTheme.typography.bodyLarge,
            modifier = Modifier
                .weight(1f)
                .padding(vertical = UnefySpacing.xs),
        )
        if (registration.isWaitlisted) {
            UnefyPill(
                text = stringResource(R.string.event_detail_waitlisted),
                container = extended.warningContainer,
                content = extended.onWarningContainer,
            )
        }
        if (canManage) {
            if (removing) {
                CircularProgressIndicator(
                    modifier = Modifier.size(PICKER_ICON),
                    strokeWidth = 2.dp,
                )
            } else {
                IconButton(onClick = onRemove, enabled = online) {
                    Icon(
                        painter = painterResource(DesignR.drawable.ic_close),
                        contentDescription = stringResource(R.string.event_detail_remove_title),
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(
            start = UnefySpacing.screen,
            end = UnefySpacing.screen,
            top = UnefySpacing.lg,
            bottom = UnefySpacing.sm,
        ),
    )
}

/**
 * The header's when-line. An all-day event has no meaningful time; a same-day
 * end collapses to "date, start–end"; anything else spells out both instants.
 */
@Composable
private fun eventTimeRange(event: Event): String {
    val end = event.endsAt
    return when {
        event.allDay -> {
            val start = UnefyFormat.date(event.startsAt)
            val endDate = end?.let(UnefyFormat::date)
            if (endDate.isNullOrBlank() || endDate == start) start else "$start – $endDate"
        }

        end == null -> UnefyFormat.dateTime(event.startsAt)

        sameDay(event.startsAt, end) ->
            "${UnefyFormat.dateTime(event.startsAt)} – ${UnefyFormat.time(end)}"

        else -> "${UnefyFormat.dateTime(event.startsAt)} – ${UnefyFormat.dateTime(end)}"
    }
}

/**
 * Same *local* calendar day — the day the person sees, not the UTC one. A
 * party ending at 00:00 local is still "22:00Z the same day", and collapsing
 * on the UTC prefix would print "13:00 – 00:00" for an overnight event.
 */
private fun sameDay(a: String, b: String): Boolean = runCatching {
    val zone = ZoneId.systemDefault()
    Instant.parse(a).atZone(zone).toLocalDate() == Instant.parse(b).atZone(zone).toLocalDate()
}.getOrElse { a.take(DATE_PREFIX) == b.take(DATE_PREFIX) }

private const val DATE_PREFIX = 10

@Composable
private fun eventTypeLabel(type: String?): String? = when (type) {
    "training" -> stringResource(R.string.event_type_training)
    "meeting" -> stringResource(R.string.event_type_meeting)
    "celebration" -> stringResource(R.string.event_type_celebration)
    "competition" -> stringResource(R.string.event_type_competition)
    // "other" says nothing a pill should repeat, and unknown types stay quiet
    // rather than leaking backend vocabulary into the UI.
    else -> null
}

@Preview
@Composable
private fun EventDetailPreview() {
    UnefyTheme {
        EventDetailScreen(
            state = EventDetailUiState.Content(
                event = Event(
                    id = "1",
                    title = "Jahreshauptversammlung 2026",
                    description = "Mit Vorstandswahl und anschließendem Essen.",
                    type = "meeting",
                    location = "Vereinsheim, großer Saal",
                    startsAt = "2026-02-20T19:00:00Z",
                    endsAt = "2026-02-20T21:30:00Z",
                    allDay = false,
                    registrationRequired = true,
                    registrationDeadline = "2026-02-18T23:59:00Z",
                    registeredCount = 12,
                    maxParticipants = 40,
                    status = "scheduled",
                    isRegistered = true,
                ),
                registrations = listOf(
                    EventRegistration("r1", "m1", "Susanne Bauer", "registered", null),
                    EventRegistration("r2", "m2", "Stefan Weber", "waitlist", null),
                ),
                detailLoaded = true,
                online = true,
                busy = false,
                now = "2026-02-01T00:00:00Z",
            ),
        )
    }
}

/** Offline: the mirror carries the event, the affordances say why they are gone. */
@Preview
@Composable
private fun EventDetailOfflinePreview() {
    UnefyTheme {
        EventDetailScreen(
            state = EventDetailUiState.Content(
                event = Event(
                    id = "1",
                    title = "Jahreshauptversammlung 2026",
                    description = null,
                    type = "meeting",
                    location = "Vereinsheim",
                    startsAt = "2026-02-20T19:00:00Z",
                    endsAt = null,
                    allDay = false,
                    registrationRequired = true,
                    registrationDeadline = null,
                    registeredCount = 0,
                    maxParticipants = 40,
                    status = "scheduled",
                    isRegistered = false,
                ),
                registrations = emptyList(),
                detailLoaded = false,
                online = false,
                busy = false,
                now = "2026-02-01T00:00:00Z",
            ),
        )
    }
}
