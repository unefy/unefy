package com.unefy.feature.events

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.hilt.navigation.compose.hiltViewModel
import java.time.Instant
import java.time.ZoneId
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.component.Field
import com.unefy.core.designsystem.component.LocalGlassBarHeight
import com.unefy.core.designsystem.component.UnefyDetailSection
import com.unefy.core.designsystem.component.UnefyPill
import com.unefy.core.designsystem.theme.LocalUnefyColors
import com.unefy.core.designsystem.theme.UnefyFormat
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.Event
import com.unefy.core.model.EventRegistration

@Composable
fun EventDetailRoute(
    eventId: String,
    onBack: () -> Unit,
    viewModel: EventDetailViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    LaunchedEffect(eventId) { viewModel.load(eventId) }
    EventDetailScreen(
        state = state,
        onBack = onBack,
        onToggleRegistration = viewModel::toggleRegistration,
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EventDetailScreen(
    state: EventDetailUiState,
    onBack: () -> Unit = {},
    onToggleRegistration: () -> Unit = {},
) {
    val scrollBehavior = TopAppBarDefaults.enterAlwaysScrollBehavior()

    Scaffold(
        modifier = Modifier.nestedScroll(scrollBehavior.nestedScrollConnection),
        topBar = {
            TopAppBar(
                scrollBehavior = scrollBehavior,
                // No title: the event names itself in the header below, and the
                // same word twice on one screen reads as a stutter.
                title = {},
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            painter = painterResource(DesignR.drawable.ic_arrow_back),
                            contentDescription = stringResource(R.string.event_detail_back),
                        )
                    }
                },
            )
        },
    ) { insets ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(insets)
                .verticalScroll(rememberScrollState()),
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
                    onToggleRegistration = onToggleRegistration,
                )
            }
            // The glass bar floats over the content; the last row must be able
            // to scroll clear of it.
            Spacer(modifier = Modifier.height(LocalGlassBarHeight.current + UnefySpacing.lg))
        }
    }
}

@Composable
private fun EventDetailContent(
    state: EventDetailUiState.Content,
    onToggleRegistration: () -> Unit,
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

    UnefyDetailSection(stringResource(R.string.event_detail_section_details)) {
        Field(stringResource(R.string.event_detail_location), event.location)
        Field(
            label = stringResource(R.string.event_detail_starts),
            value = if (event.allDay) {
                UnefyFormat.date(event.startsAt)
            } else {
                UnefyFormat.dateTime(event.startsAt)
            },
            mono = true,
        )
        Field(
            label = stringResource(R.string.event_detail_ends),
            value = event.endsAt?.let {
                if (event.allDay) UnefyFormat.date(it) else UnefyFormat.dateTime(it)
            },
            mono = true,
        )
        Field(
            label = stringResource(R.string.event_detail_deadline),
            value = event.registrationDeadline?.let(UnefyFormat::dateTime),
            mono = true,
        )
        Field(stringResource(R.string.event_detail_competition), event.competitionName)
    }

    if (state.detailLoaded && state.registrations.isNotEmpty()) {
        SectionTitle(
            stringResource(R.string.event_detail_section_participants, state.registrations.size),
        )
        state.registrations.forEach { registration ->
            ParticipantRow(registration)
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        }
    }
}

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
private fun ParticipantRow(registration: EventRegistration) {
    val extended = LocalUnefyColors.current
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.md),
        horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = registration.memberName
                ?: stringResource(R.string.event_detail_participant_unknown),
            style = MaterialTheme.typography.bodyLarge,
            modifier = Modifier.weight(1f),
        )
        if (registration.isWaitlisted) {
            UnefyPill(
                text = stringResource(R.string.event_detail_waitlisted),
                container = extended.warningContainer,
                content = extended.onWarningContainer,
            )
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
                    EventRegistration("r2", "m2", "Stefan Weber", "waitlisted", null),
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
