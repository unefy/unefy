package com.unefy.feature.attendance

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.component.UnefyListScaffold
import com.unefy.core.designsystem.theme.LocalUnefyColors
import com.unefy.core.designsystem.theme.UnefyMotion
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.ClubRole
import com.unefy.feature.attendance.nfc.AntennaHint

@Composable
fun MemberCodeRoute(
    role: ClubRole,
    onOpenScanner: () -> Unit,
    actions: @Composable RowScope.() -> Unit = {},
    viewModel: MemberCodeViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    MemberCodeScreen(
        state = state,
        // The backend gates scanning on board and above, so offering it to a
        // member would only produce a 403 at the far end of a camera session.
        canScan = role.canAdminister,
        actions = actions,
        onOpenScanner = onOpenScanner,
        onRetry = viewModel::retry,
    )
}

@Composable
fun MemberCodeScreen(
    state: MemberCodeUiState,
    canScan: Boolean = false,
    actions: @Composable RowScope.() -> Unit = {},
    onOpenScanner: () -> Unit = {},
    onRetry: () -> Unit = {},
) {
    UnefyListScaffold(
        title = stringResource(R.string.attendance_code_title),
        actions = {
            // Ahead of the account actions: on a training evening this is the
            // button a supervisor reaches for, and it belongs next to the
            // content rather than at the end of a row of avatars.
            if (canScan) {
                IconButton(onClick = onOpenScanner) {
                    Icon(
                        painter = painterResource(DesignR.drawable.ic_qr_scanner),
                        contentDescription = stringResource(R.string.attendance_open_scanner),
                    )
                }
            }
            actions()
        },
    ) {
        when (state) {
            MemberCodeUiState.Loading -> Unit

            is MemberCodeUiState.Content -> item("code") { CodeCard(state) }

            // Deliberately not the confirmation: nothing is confirmed yet, and
            // showing a tick that might turn into a refusal is worse than a
            // second of honest waiting.
            MemberCodeUiState.Read -> item("read") {
                Message(
                    title = stringResource(R.string.attendance_code_read_title),
                    body = stringResource(R.string.attendance_code_read_body),
                )
            }

            is MemberCodeUiState.Confirmed -> item("confirmed") { Confirmation(state.sessionTitle) }

            MemberCodeUiState.NoMembership -> item("no-membership") {
                Message(
                    title = stringResource(R.string.attendance_code_no_membership_title),
                    body = stringResource(R.string.attendance_code_no_membership_body),
                )
            }

            is MemberCodeUiState.Failure -> item("error") {
                Message(
                    title = stringResource(R.string.attendance_code_error_title),
                    body = stringResource(R.string.attendance_code_error_body),
                    onRetry = onRetry,
                )
            }
        }
    }
}

@Composable
private fun CodeCard(state: MemberCodeUiState.Content) {
    // Full brightness for as long as this screen is up. A dimmed panel is the
    // usual reason a code will not scan in a badly lit hall.
    KeepScreenBrightAndAwake()

    Column(
        modifier = Modifier.padding(horizontal = UnefySpacing.screen),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(UnefySpacing.lg),
    ) {
        Text(
            text = stringResource(R.string.attendance_code_hint),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )

        // Always white on black, never the theme's colours: a scanner needs
        // contrast and a fixed polarity, and an inverted code in dark mode is
        // one many readers refuse.
        Surface(
            shape = MaterialTheme.shapes.extraLarge,
            color = QR_BACKGROUND,
            modifier = Modifier.fillMaxWidth(),
        ) {
            // Crossfade rather than a hard swap. The code changes twice a
            // minute while someone is holding the phone still, and an abrupt
            // redraw reads as a glitch — a short dissolve reads as a refresh.
            // Deliberately quick: a scanner must not spend long looking at two
            // half-faded codes on top of each other.
            AnimatedContent(
                targetState = state.code,
                transitionSpec = { fadeIn(UnefyMotion.effects()) togetherWith fadeOut(UnefyMotion.effects()) },
                label = "attendance-code",
            ) { code ->
                QrCode(
                    content = code,
                    foreground = QR_FOREGROUND,
                    background = QR_BACKGROUND,
                    modifier = Modifier
                        .padding(UnefySpacing.lg)
                        .aspectRatio(1f),
                )
            }
        }

        CodeCountdown(state.secondsRemaining)

        // The other phone cannot be told where this one's antenna is, so each
        // shows its own and the two people meet in the middle.
        AntennaHint(modifier = Modifier.fillMaxWidth())

        if (state.seedStale) {
            Text(
                text = stringResource(R.string.attendance_code_offline),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
        }
    }
}

/**
 * A ring that empties as the code ages, with the seconds in the middle.
 *
 * Not decoration: a still screenshot and a live code look identical, and this is
 * the only thing telling a member which one they are holding out. A ring rather
 * than a bar because it reads as a clock at a glance from arm's length, which is
 * exactly the distance this screen is looked at from.
 */
@Composable
private fun CodeCountdown(secondsRemaining: Long) {
    // Animated, so the ring sweeps instead of stepping once a second. The
    // duration matches the tick, so it arrives exactly as the next one starts.
    val progress by animateFloatAsState(
        targetValue = secondsRemaining.toFloat() / AttendanceCode.INTERVAL_SECONDS,
        animationSpec = tween(durationMillis = TICK_MILLIS, easing = LinearEasing),
        label = "countdown",
    )

    Box(contentAlignment = Alignment.Center) {
        CircularProgressIndicator(
            progress = { progress },
            modifier = Modifier.size(RING_SIZE),
            strokeWidth = RING_STROKE,
            trackColor = MaterialTheme.colorScheme.surfaceContainerHighest,
            // No gap and a butt cap: the ring is a depleting quantity, not a
            // set of segments.
            gapSize = 0.dp,
            strokeCap = StrokeCap.Butt,
        )
        Text(
            text = "$secondsRemaining",
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

private val RING_SIZE = 56.dp
private val RING_STROKE = 3.dp
private const val TICK_MILLIS = 1_000

/**
 * The code did its job.
 *
 * Replaces the QR outright rather than adding a line to it: holding out a code
 * that has already been used invites a second scan, and the member's question
 * is answered — they can put the phone away.
 */
@Composable
private fun Confirmation(sessionTitle: String?) {
    val colors = LocalUnefyColors.current
    val haptics = LocalHapticFeedback.current
    LaunchedEffect(Unit) { haptics.performHapticFeedback(HapticFeedbackType.Confirm) }

    Surface(
        shape = MaterialTheme.shapes.extraLarge,
        color = colors.successContainer,
        modifier = Modifier
            .fillMaxWidth()
            .padding(UnefySpacing.screen),
    ) {
        Column(
            modifier = Modifier.padding(UnefySpacing.xl),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(UnefySpacing.md),
        ) {
            Icon(
                painter = painterResource(DesignR.drawable.ic_check),
                contentDescription = null,
                tint = colors.onSuccessContainer,
                modifier = Modifier.size(CONFIRM_ICON),
            )
            Text(
                text = stringResource(R.string.attendance_code_confirmed),
                style = MaterialTheme.typography.headlineSmall,
                color = colors.onSuccessContainer,
                textAlign = TextAlign.Center,
            )
            sessionTitle?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.bodyMedium,
                    color = colors.onSuccessContainer,
                    textAlign = TextAlign.Center,
                )
            }
        }
    }
}

private val CONFIRM_ICON = 48.dp

@Composable
private fun Message(title: String, body: String, onRetry: (() -> Unit)? = null) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(UnefySpacing.lg),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
    ) {
        Text(text = title, style = MaterialTheme.typography.titleMedium)
        Text(
            text = body,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        onRetry?.let {
            Box(modifier = Modifier.padding(top = UnefySpacing.sm)) {
                Button(onClick = it) { Text(stringResource(R.string.attendance_retry)) }
            }
        }
    }
}

private val QR_FOREGROUND = androidx.compose.ui.graphics.Color.Black
private val QR_BACKGROUND = androidx.compose.ui.graphics.Color.White

@Preview
@Composable
private fun MemberCodePreview() {
    UnefyTheme {
        MemberCodeScreen(
            state = MemberCodeUiState.Content(
                code = "uf1.AAAAAAAAAAAAAAAA.59448240.VW54OV2ZM3OO4N6X",
                secondsRemaining = 18,
                seedStale = false,
            ),
            canScan = true,
        )
    }
}
