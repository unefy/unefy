package com.unefy.feature.attendance

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.compose.CameraXViewfinder
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.component.UnefyListScaffold
import com.unefy.core.designsystem.theme.LocalUnefyColors
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.feature.attendance.nfc.CheckInApdu
import com.unefy.feature.attendance.nfc.NfcReader
import com.unefy.feature.attendance.nfc.NfcState
import com.unefy.feature.attendance.nfc.TapResult

@Composable
fun ScannerRoute(
    onBack: () -> Unit,
    actions: @Composable RowScope.() -> Unit = {},
    onOpenAttendanceList: (sessionId: String, sessionTitle: String) -> Unit = { _, _ -> },
    viewModel: ScannerViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current
    // Resolved here rather than in the view model, which has no resources.
    val defaultTitle = stringResource(R.string.scanner_default_session_title)

    var granted by rememberSaveable {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED,
        )
    }
    val requestPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted = it }

    ScannerScreen(
        state = state,
        cameraGranted = granted,
        actions = actions,
        onBack = onBack,
        onGrantCamera = { requestPermission.launch(Manifest.permission.CAMERA) },
        onSelectSession = viewModel::selectSession,
        onRetrySessions = viewModel::loadSessions,
        bindCamera = viewModel::bindToCamera,
        onOpenManual = viewModel::openManualPick,
        onCloseManual = viewModel::closeManualPick,
        onManualQueryChange = viewModel::onManualQueryChange,
        onCheckInManually = viewModel::checkInManually,
        onGuestNameChange = viewModel::onGuestNameChange,
        onCheckInGuest = { viewModel.checkInGuest(state.manual.guestName) },
        onCreateSession = { viewModel.createSessionForToday(defaultTitle) },
        onCodeTapped = viewModel::onCodeTapped,
        onTapNotReady = viewModel::onTapNotReady,
        onTagDetected = viewModel::onTagDetected,
        onNfcState = viewModel::onNfcState,
        onRefresh = viewModel::refresh,
        onOpenAttendance = {
            state.sessions.firstOrNull { it.id == state.selectedSessionId }?.let { session ->
                onOpenAttendanceList(session.id, session.title)
            }
        },
    )
}

@Composable
fun ScannerScreen(
    state: ScannerUiState,
    cameraGranted: Boolean,
    actions: @Composable RowScope.() -> Unit = {},
    onBack: () -> Unit = {},
    onGrantCamera: () -> Unit = {},
    onSelectSession: (String) -> Unit = {},
    onRetrySessions: () -> Unit = {},
    bindCamera: suspend (android.content.Context, androidx.lifecycle.LifecycleOwner) -> Unit =
        { _, _ -> },
    onOpenManual: () -> Unit = {},
    onCloseManual: () -> Unit = {},
    onManualQueryChange: (String) -> Unit = {},
    onCheckInManually: (MemberPick) -> Unit = {},
    onGuestNameChange: (String) -> Unit = {},
    onCheckInGuest: () -> Unit = {},
    onCreateSession: () -> Unit = {},
    onCodeTapped: (String, (CheckInApdu.Outcome) -> Unit) -> Unit = { _, _ -> },
    onTapNotReady: () -> Unit = {},
    onTagDetected: () -> Unit = {},
    onNfcState: (NfcState) -> Unit = {},
    onRefresh: () -> Unit = {},
    onOpenAttendance: () -> Unit = {},
) {
    // The scanner is only a reader while it is on screen, so letting the phone
    // lock during an evening silently ends check-in.
    KeepScreenAwake()

    // Reloaded every time this screen comes forward. Until now the list only
    // moved when this device checked somebody in, so a correction made in the
    // web app — or by another supervisor's phone — was invisible here for as
    // long as the screen stayed open.
    RefreshOnResume(onRefresh)

    // Outside the list, not in an item of it. Reader mode has to live as long
    // as this screen does, and a lazy list disposes what scrolls away — mounting
    // it in a zero-height row made "is NFC even on?" depend on scroll position.
    // Alongside the camera, not instead of it: a member holds out either a
    // screen or a phone back, and the supervisor should not have to know which
    // before pointing at it.
    NfcReader(
        enabled = state.selectedSessionId != null,
        onDetected = onTagDetected,
        onState = onNfcState,
    ) { tap ->
        when (tap) {
            is TapResult.Code -> onCodeTapped(tap.value, tap.respond)
            TapResult.NotReady -> onTapNotReady()
            TapResult.Foreign -> Unit
        }
    }

    if (state.manual.open) {
        ManualPickSheet(
            state = state.manual,
            onQueryChange = onManualQueryChange,
            onPick = onCheckInManually,
            onGuestNameChange = onGuestNameChange,
            onCheckInGuest = onCheckInGuest,
            onDismiss = onCloseManual,
        )
    }

    UnefyListScaffold(
        title = stringResource(R.string.scanner_title),
        // Reached from the check-in screen, so it needs a way back. Back belongs
        // on the left on Android, which is what the leading slot is for.
        navigationIcon = {
            IconButton(onClick = onBack) {
                Icon(
                    painter = painterResource(DesignR.drawable.ic_arrow_back),
                    contentDescription = stringResource(R.string.scanner_back),
                )
            }
        },
        actions = {
            // Only with a session to check into — the action would otherwise
            // open a list that cannot do anything.
            if (state.selectedSessionId != null) {
                TextButton(onClick = onOpenManual) {
                    Text(stringResource(R.string.scanner_manual_action))
                }
            }
            actions()
        },
    ) {
        when {
            state.sessionsError != null -> item("error") {
                Message(
                    title = stringResource(R.string.scanner_sessions_error_title),
                    body = stringResource(R.string.scanner_sessions_error_body),
                    action = stringResource(R.string.attendance_retry) to onRetrySessions,
                )
            }

            state.loadingSessions -> Unit

            state.sessions.isEmpty() -> item("empty") {
                Message(
                    title = stringResource(R.string.scanner_no_sessions_title),
                    // With no session there is nothing to check into, and the
                    // supervisor is standing at the range. Sending them to a
                    // laptop is how an evening goes unrecorded.
                    body = stringResource(R.string.scanner_no_sessions_body),
                    action = stringResource(R.string.scanner_create_session) to onCreateSession,
                )
            }

            else -> scannerContent(
                state = state,
                cameraGranted = cameraGranted,
                onGrantCamera = onGrantCamera,
                onSelectSession = onSelectSession,
                bindCamera = bindCamera,
                onOpenAttendance = onOpenAttendance,
            )
        }
    }
}

private fun LazyListScope.scannerContent(
    state: ScannerUiState,
    cameraGranted: Boolean,
    onGrantCamera: () -> Unit,
    onSelectSession: (String) -> Unit,
    bindCamera: suspend (android.content.Context, androidx.lifecycle.LifecycleOwner) -> Unit,
    onOpenAttendance: () -> Unit,
) {
    // Only when there is a choice. One open training evening is the normal
    // case, and a single chip to pick from is noise.
    if (state.sessions.size > 1) {
        item("sessions") {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = UnefySpacing.screen, vertical = UnefySpacing.sm),
                horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
            ) {
                state.sessions.forEach { session ->
                    FilterChip(
                        selected = session.id == state.selectedSessionId,
                        onClick = { onSelectSession(session.id) },
                        label = { Text(session.title) },
                    )
                }
            }
        }
    }

    item("viewfinder") {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = UnefySpacing.screen)
                .aspectRatio(1f),
            contentAlignment = Alignment.Center,
        ) {
            if (cameraGranted) {
                Viewfinder(state = state, bindCamera = bindCamera)
            } else {
                Message(
                    title = stringResource(R.string.scanner_permission_title),
                    body = stringResource(R.string.scanner_permission_body),
                    action = stringResource(R.string.scanner_permission_action) to onGrantCamera,
                )
            }
        }
    }

    item("nfc-hint") {
        Text(
            text = when (state.nfc) {
                NfcState.Listening -> stringResource(R.string.scanner_nfc_hint)
                NfcState.SwitchedOff -> stringResource(R.string.scanner_nfc_off)
                NfcState.Unavailable -> stringResource(R.string.scanner_nfc_unavailable)
                NfcState.Idle -> stringResource(R.string.scanner_nfc_idle)
            },
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(horizontal = UnefySpacing.screen),
        )
    }

    item("feedback") {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(UnefySpacing.screen),
            verticalArrangement = Arrangement.spacedBy(UnefySpacing.xs),
        ) {
            FeedbackBanner(
                // "Bereit" would be a lie while nothing is selected: a scan is
                // dropped on the floor without a session, and the chips above
                // do not explain themselves.
                text = if (state.selectedSessionId == null) {
                    stringResource(R.string.scanner_pick_session)
                } else {
                    feedbackText(state.feedback)
                },
                feedback = state.feedback.takeIf { state.selectedSessionId != null },
            )
            // The list itself lives one screen further: with discipline, weapon
            // and round count on every row it became data entry, and data entry
            // does not belong in the space left over under a camera. Here stays
            // what the scanner needs — the count, and the way there.
            if (state.selectedSessionId != null) {
                TextButton(onClick = onOpenAttendance) {
                    Text(
                        stringResource(
                            R.string.scanner_attendance_list,
                            state.checkedInCount,
                        ),
                    )
                }
            }

            // Visible whenever anything is held. A queue nobody can see is a
            // queue nobody notices failing to drain, and these check-ins exist
            // on this phone and nowhere else.
            if (state.pending > 0) {
                Text(
                    text = pluralStringResource(
                        R.plurals.scanner_pending,
                        state.pending,
                        state.pending,
                    ),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }

}

/**
 * The scan result, as a coloured surface rather than a line of text.
 *
 * The supervisor is looking at the viewfinder and the person in front of them,
 * not at a paragraph — a sentence that merely changes wording is missed, and a
 * missed rejection means somebody walks in unrecorded. Colour carries it at a
 * glance, the words carry the detail, and the haptic carries it when the phone
 * is not being looked at at all.
 *
 * Hue is reserved for status in this design system, which is exactly this.
 */
/** Runs [onRefresh] whenever this screen comes to the foreground. */
@Composable
internal fun RefreshOnResume(onRefresh: () -> Unit) {
    val lifecycleOwner = LocalLifecycleOwner.current
    val current by rememberUpdatedState(onRefresh)

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) current()
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
}

@Composable
private fun FeedbackBanner(text: String, feedback: ScanFeedback?) {
    val colors = LocalUnefyColors.current
    val container = when (feedback) {
        is ScanFeedback.CheckedIn -> colors.successContainer
        is ScanFeedback.QueuedOffline, ScanFeedback.AlreadyPresent,
        ScanFeedback.Busy,
        -> colors.warningContainer

        ScanFeedback.Detected -> MaterialTheme.colorScheme.secondaryContainer

        ScanFeedback.CodeUsed, ScanFeedback.CodeInvalid, ScanFeedback.Offline,
        ScanFeedback.CardNotReady, ScanFeedback.NoSessionChosen, is ScanFeedback.Failed,
        -> MaterialTheme.colorScheme.errorContainer

        null -> MaterialTheme.colorScheme.surfaceContainer
    }
    val content = when (feedback) {
        is ScanFeedback.CheckedIn -> colors.onSuccessContainer
        is ScanFeedback.QueuedOffline, ScanFeedback.AlreadyPresent,
        ScanFeedback.Busy,
        -> colors.onWarningContainer

        ScanFeedback.Detected -> MaterialTheme.colorScheme.onSecondaryContainer

        ScanFeedback.CodeUsed, ScanFeedback.CodeInvalid, ScanFeedback.Offline,
        ScanFeedback.CardNotReady, ScanFeedback.NoSessionChosen, is ScanFeedback.Failed,
        -> MaterialTheme.colorScheme.onErrorContainer

        null -> MaterialTheme.colorScheme.onSurfaceVariant
    }

    val haptics = LocalHapticFeedback.current
    LaunchedEffect(feedback) {
        // Keyed on the result object, so a second scan of the same outcome
        // still buzzes — otherwise two people in a row would feel like one.
        when (feedback) {
            null -> Unit
            // Distinct from both outcomes: this one means "keep holding".
            ScanFeedback.Detected -> haptics.performHapticFeedback(HapticFeedbackType.ContextClick)
            is ScanFeedback.CheckedIn -> haptics.performHapticFeedback(HapticFeedbackType.Confirm)
            else -> haptics.performHapticFeedback(HapticFeedbackType.Reject)
        }
    }

    Surface(
        shape = MaterialTheme.shapes.large,
        color = container,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.titleMedium,
            color = content,
            modifier = Modifier.padding(UnefySpacing.md),
        )
    }
}

@Composable
private fun Viewfinder(
    state: ScannerUiState,
    bindCamera: suspend (android.content.Context, androidx.lifecycle.LifecycleOwner) -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    // Keyed on nothing that changes per frame: the binding must survive
    // recomposition, and cancelling it is what releases the camera when the
    // screen goes away.
    LaunchedEffect(lifecycleOwner) { bindCamera(context.applicationContext, lifecycleOwner) }

    val request = state.surfaceRequest
    Surface(shape = MaterialTheme.shapes.large, modifier = Modifier.fillMaxSize()) {
        if (request != null) {
            CameraXViewfinder(surfaceRequest = request, modifier = Modifier.fillMaxSize())
        }
    }
}

@Composable
private fun feedbackText(feedback: ScanFeedback?): String = when (feedback) {
    null -> stringResource(R.string.scanner_waiting)

    is ScanFeedback.CheckedIn -> stringResource(
        R.string.scanner_checked_in,
        feedback.memberName ?: stringResource(R.string.scanner_unknown_member),
    )

    ScanFeedback.AlreadyPresent -> stringResource(R.string.scanner_already_present)
    ScanFeedback.CodeUsed -> stringResource(R.string.scanner_code_used)
    ScanFeedback.CodeInvalid -> stringResource(R.string.scanner_code_invalid)
    ScanFeedback.Offline -> stringResource(R.string.scanner_offline)
    ScanFeedback.CardNotReady -> stringResource(R.string.scanner_card_not_ready)
    ScanFeedback.NoSessionChosen -> stringResource(R.string.scanner_pick_session)
    ScanFeedback.Busy -> stringResource(R.string.scanner_busy)
    ScanFeedback.Detected -> stringResource(R.string.scanner_detected)

    is ScanFeedback.QueuedOffline -> stringResource(
        R.string.scanner_queued,
        feedback.memberLabel ?: stringResource(R.string.scanner_unknown_member),
    )
    is ScanFeedback.Failed -> stringResource(R.string.scanner_failed)
}

@Composable
private fun Message(title: String, body: String, action: Pair<String, () -> Unit>? = null) {
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
        action?.let { (label, onClick) ->
            Button(onClick = onClick) { Text(label) }
        }
    }
}

@Preview
@Composable
private fun ScannerPreview() {
    UnefyTheme {
        ScannerScreen(
            state = ScannerUiState(
                sessions = listOf(AttendanceSessionSummary("1", "Übungsabend", "Stand 1", 4)),
                selectedSessionId = "1",
                loadingSessions = false,
                feedback = ScanFeedback.CheckedIn("Alice Example", "001"),
                checkedInCount = 4,
            ),
            cameraGranted = false,
        )
    }
}
