package com.unefy.feature.attendance

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.unefy.core.designsystem.component.UnefyListScaffold
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme

@Composable
fun MemberCodeRoute(
    actions: @Composable RowScope.() -> Unit = {},
    viewModel: MemberCodeViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    MemberCodeScreen(state = state, actions = actions, onRetry = viewModel::retry)
}

@Composable
fun MemberCodeScreen(
    state: MemberCodeUiState,
    actions: @Composable RowScope.() -> Unit = {},
    onRetry: () -> Unit = {},
) {
    UnefyListScaffold(title = stringResource(R.string.attendance_code_title), actions = actions) {
        when (state) {
            MemberCodeUiState.Loading -> Unit

            is MemberCodeUiState.Content -> item("code") { CodeCard(state) }

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
    Column(
        modifier = Modifier.padding(UnefySpacing.screen),
        verticalArrangement = Arrangement.spacedBy(UnefySpacing.md),
    ) {
        Text(
            text = stringResource(R.string.attendance_code_hint),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        // Always white on black, never the theme's colours: a scanner needs
        // contrast and a fixed polarity, and an inverted code in dark mode is
        // one many readers refuse.
        Surface(
            shape = MaterialTheme.shapes.large,
            color = QR_BACKGROUND,
            modifier = Modifier.fillMaxWidth(),
        ) {
            QrCode(
                content = state.code,
                foreground = QR_FOREGROUND,
                background = QR_BACKGROUND,
                modifier = Modifier
                    .padding(UnefySpacing.lg)
                    .aspectRatio(1f),
            )
        }

        // The countdown is not decoration: without it a still image and a live
        // code look identical, and a member cannot tell a frozen screen from a
        // working one.
        LinearProgressIndicator(
            progress = { state.secondsRemaining.toFloat() / AttendanceCode.INTERVAL_SECONDS },
            modifier = Modifier.fillMaxWidth(),
        )
        Text(
            text = stringResource(
                R.string.attendance_code_refresh_in,
                state.secondsRemaining.toInt(),
            ),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        if (state.seedStale) {
            Text(
                text = stringResource(R.string.attendance_code_offline),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

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
        )
    }
}
