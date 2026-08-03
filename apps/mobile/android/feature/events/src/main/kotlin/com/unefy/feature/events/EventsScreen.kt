package com.unefy.feature.events

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.theme.LocalUnefyColors
import com.unefy.core.designsystem.theme.UnefyFormat
import com.unefy.core.designsystem.component.UnefyListScaffold
import com.unefy.core.designsystem.component.UnefyStaleBanner
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.Event
import com.unefy.core.network.ApiError

@Composable
fun EventsRoute(
    onEventClick: (String) -> Unit,
    actions: @Composable RowScope.() -> Unit = {},
    viewModel: EventsViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    EventsScreen(
        state = state,
        actions = actions,
        onEventClick = onEventClick,
        onRetry = viewModel::retry,
        onToggleRegistration = viewModel::toggleRegistration,
        onRefresh = viewModel::refresh,
    )
}

@Composable
fun EventsScreen(
    state: EventsUiState,
    actions: @Composable RowScope.() -> Unit = {},
    onEventClick: (String) -> Unit = {},
    onRetry: () -> Unit = {},
    onToggleRegistration: (Event) -> Unit = {},
    onRefresh: () -> Unit = {},
) {
    val content = state as? EventsUiState.Content

    UnefyListScaffold(
        title = stringResource(R.string.events_title),
        actions = actions,
        isRefreshing = content?.isRefreshing == true,
        onRefresh = onRefresh,
        // No onLoadMore. The mirror holds the whole calendar, so scrolling has
        // nothing to fetch.
        banner = {
            val stale = content?.staleBecause
            UnefyStaleBanner(
                visible = stale != null,
                text = stringResource(
                    if (stale is ApiError.Network) {
                        DesignR.string.stale_offline
                    } else {
                        DesignR.string.stale_generic
                    },
                ),
            )
        },
    ) {
        when (state) {
            EventsUiState.Loading -> Unit

            is EventsUiState.Failure -> item {
                Centered(
                    title = stringResource(R.string.events_error_title),
                    body = stringResource(R.string.events_error_body),
                    modifier = Modifier.fillParentMaxHeight(FILL_BELOW_HEADING),
                    action = {
                        OutlinedButton(onClick = onRetry) {
                            Text(stringResource(R.string.events_retry))
                        }
                    },
                )
            }

            is EventsUiState.Content -> if (state.upcoming.isEmpty() && state.past.isEmpty()) {
                item {
                    Centered(
                        title = stringResource(R.string.events_empty_title),
                        body = stringResource(R.string.events_empty_body),
                        modifier = Modifier.fillParentMaxHeight(FILL_BELOW_HEADING),
                    )
                }
            } else {
                if (state.upcoming.isNotEmpty()) {
                    item(key = "upcoming") {
                        // First section sits right under the header; later ones
                        // need the full gap to read as a break.
                        SectionHeader(stringResource(R.string.events_upcoming), UnefySpacing.sm)
                    }
                    items(state.upcoming, key = { it.id }) { event ->
                        EventRow(
                            event = event,
                            dimmed = false,
                            busy = event.id in state.pending,
                            // Capacity and registration state exist only where the
                            // online overlay answered — never claim "0 of 40" for
                            // a row the mirror alone knows.
                            showRegistration = event.id in state.overlaid,
                            canRegister = state.online &&
                                event.id in state.overlaid &&
                                event.registrationOpen(state.now),
                            onToggleRegistration = { onToggleRegistration(event) },
                            onClick = { onEventClick(event.id) },
                        )
                    }
                }
                if (state.past.isNotEmpty()) {
                    item(key = "past") { SectionHeader(stringResource(R.string.events_past)) }
                    // No registration control on past events — the action is
                    // meaningless there.
                    items(state.past, key = { it.id }) {
                        EventRow(event = it, dimmed = true, onClick = { onEventClick(it.id) })
                    }
                }
            }
        }
    }
}

@Composable
private fun SectionHeader(text: String, topPadding: Dp = UnefySpacing.lg) {
    Text(
        text = text,
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(
            start = UnefySpacing.screen,
            end = UnefySpacing.screen,
            top = topPadding,
            bottom = UnefySpacing.sm,
        ),
    )
}

@Composable
private fun EventRow(
    event: Event,
    dimmed: Boolean,
    busy: Boolean = false,
    /** Whether the overlay knows this event — pill and buttons only then. */
    showRegistration: Boolean = false,
    canRegister: Boolean = false,
    onToggleRegistration: (() -> Unit)? = null,
    onClick: () -> Unit = {},
) {
    val titleColor = if (dimmed) {
        MaterialTheme.colorScheme.onSurfaceVariant
    } else {
        MaterialTheme.colorScheme.onSurface
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.md),
        verticalArrangement = Arrangement.spacedBy(UnefySpacing.xs),
    ) {
        Text(
            // An all-day event has no meaningful time — the backend stores
            // midnight UTC, which renders as 02:00 in Berlin.
            text = if (event.allDay) {
                UnefyFormat.date(event.startsAt)
            } else {
                UnefyFormat.dateTime(event.startsAt)
            },
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = event.title,
            style = MaterialTheme.typography.titleMedium,
            color = titleColor,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        event.location?.let {
            Text(
                text = it,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        if (event.registrationRequired && showRegistration) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(top = UnefySpacing.xs),
            ) {
                RegistrationPill(event)

                onToggleRegistration?.let { toggle ->
                    when {
                        // Cancelling stays available even past the deadline —
                        // the backend allows it, and a member who cannot get out
                        // of an event has a worse problem than a late sign-up.
                        event.isRegistered -> OutlinedButton(onClick = toggle, enabled = !busy) {
                            Text(stringResource(R.string.events_unregister))
                        }

                        canRegister -> Button(onClick = toggle, enabled = !busy) {
                            Text(stringResource(R.string.events_register))
                        }

                        // Neither button: offering one that is certain to fail
                        // with a 409 is worse than saying why it is closed.
                        else -> Text(
                            text = stringResource(R.string.events_registration_closed),
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
    }
    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
}

/**
 * Capacity as a pill. Full events use the warning role rather than error: a
 * booked-out event is a state, not a failure.
 */
@Composable
private fun RegistrationPill(event: Event) {
    val extended = LocalUnefyColors.current
    val full = event.capacityRatio?.let { it >= 1f } == true
    val label = event.maxParticipants
        ?.let { stringResource(R.string.events_registered_of, event.registeredCount, it) }
        ?: stringResource(R.string.events_registered, event.registeredCount)

    Surface(
        shape = CircleShape,
        color = if (full) extended.warningContainer else MaterialTheme.colorScheme.surfaceContainerHighest,
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = if (full) extended.onWarningContainer else MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
        )
    }
}

@Composable
private fun Centered(
    title: String,
    body: String,
    modifier: Modifier = Modifier,
    action: (@Composable () -> Unit)? = null,
) {
    Column(
        modifier = modifier.fillMaxWidth().padding(UnefySpacing.lg),
        verticalArrangement = Arrangement.spacedBy(UnefySpacing.sm, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(title, style = MaterialTheme.typography.headlineSmall)
        Text(
            text = body,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        action?.invoke()
    }
}

@Preview
@Composable
private fun EventsPreview() {
    UnefyTheme {
        EventsScreen(
            state = EventsUiState.Content(
                upcoming = listOf(
                    Event(
                        id = "1",
                        title = "Jahreshauptversammlung 2026",
                        description = null,
                        type = "meeting",
                        location = "Vereinsheim, großer Saal",
                        startsAt = "2026-02-20T19:00:00Z",
                        endsAt = null,
                        allDay = false,
                        registrationRequired = true,
                        registrationDeadline = null,
                        registeredCount = 12,
                        maxParticipants = 40,
                        status = "planned",
                        isRegistered = false,
                    ),
                ),
                past = emptyList(),
                now = "2026-02-01T00:00:00Z",
                overlaid = setOf("1"),
                online = true,
            ),
        )
    }
}

/** Offline: rows from the mirror, no capacity pill, and the stale banner up top. */
@Preview
@Composable
private fun EventsOfflinePreview() {
    UnefyTheme {
        EventsScreen(
            state = EventsUiState.Content(
                upcoming = listOf(
                    Event(
                        id = "1",
                        title = "Jahreshauptversammlung 2026",
                        description = null,
                        type = "meeting",
                        location = "Vereinsheim, großer Saal",
                        startsAt = "2026-02-20T19:00:00Z",
                        endsAt = null,
                        allDay = false,
                        registrationRequired = true,
                        registrationDeadline = null,
                        registeredCount = 0,
                        maxParticipants = 40,
                        status = "planned",
                        isRegistered = false,
                    ),
                ),
                past = emptyList(),
                now = "2026-02-01T00:00:00Z",
                online = false,
                staleBecause = ApiError.Network(java.io.IOException()),
            ),
        )
    }
}

/** Empty and error states fill what is left below the heading, not the window. */
private const val FILL_BELOW_HEADING = 0.7f
