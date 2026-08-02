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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
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
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme

@Composable
fun ScannerRoute(
    onBack: () -> Unit,
    actions: @Composable RowScope.() -> Unit = {},
    viewModel: ScannerViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current

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
) {
    if (state.manual.open) {
        ManualPickSheet(
            state = state.manual,
            onQueryChange = onManualQueryChange,
            onPick = onCheckInManually,
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
                    body = stringResource(R.string.scanner_no_sessions_body),
                )
            }

            else -> scannerContent(state, cameraGranted, onGrantCamera, onSelectSession, bindCamera)
        }
    }
}

private fun LazyListScope.scannerContent(
    state: ScannerUiState,
    cameraGranted: Boolean,
    onGrantCamera: () -> Unit,
    onSelectSession: (String) -> Unit,
    bindCamera: suspend (android.content.Context, androidx.lifecycle.LifecycleOwner) -> Unit,
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

    item("feedback") {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(UnefySpacing.screen),
            verticalArrangement = Arrangement.spacedBy(UnefySpacing.xs),
        ) {
            Text(
                // "Bereit" would be a lie while nothing is selected: a scan is
                // dropped on the floor without a session, and the chips above
                // do not explain themselves.
                text = if (state.selectedSessionId == null) {
                    stringResource(R.string.scanner_pick_session)
                } else {
                    feedbackText(state.feedback)
                },
                style = MaterialTheme.typography.titleMedium,
            )
            if (state.selectedSessionId != null) {
                Text(
                    text = stringResource(R.string.scanner_counted, state.checkedInCount),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
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
