package com.unefy.app.ui.login

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.activity.compose.LocalActivity
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.layout.Row
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.unefy.app.R
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.designsystem.theme.UnefyTheme

private const val CODE_LENGTH = 6

@Composable
fun LoginRoute(viewModel: LoginViewModel = hiltViewModel()) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    // Credential Manager needs the Activity to show its account sheet; the
    // application context would throw.
    val activity = LocalActivity.current
    LoginScreen(
        state = state,
        onEmailChange = viewModel::onEmailChange,
        onCodeChange = viewModel::onCodeChange,
        onEditEmail = viewModel::editEmail,
        onSubmit = viewModel::submit,
        onGoogleSignIn = { activity?.let(viewModel::signInWithGoogle) },
        onServerChange = viewModel::useServer,
        onServerReset = viewModel::useDefaultServer,
    )
}

@Composable
fun LoginScreen(
    state: LoginUiState,
    onEmailChange: (String) -> Unit = {},
    onCodeChange: (String) -> Unit = {},
    onEditEmail: () -> Unit = {},
    onSubmit: () -> Unit = {},
    onGoogleSignIn: () -> Unit = {},
    onServerChange: (String) -> Unit = {},
    onServerReset: () -> Unit = {},
) {
    var choosingServer by remember { mutableStateOf(false) }

    if (choosingServer) {
        ServerDialog(
            current = state.serverUrl,
            onDismiss = { choosingServer = false },
            onConfirm = { choosingServer = false; onServerChange(it) },
            onReset = { choosingServer = false; onServerReset() },
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .safeDrawingPadding()
            .imePadding()
            .padding(UnefySpacing.lg),
        verticalArrangement = Arrangement.spacedBy(UnefySpacing.md, Alignment.CenterVertically),
    ) {
        Text(
            text = stringResource(R.string.login_title),
            style = MaterialTheme.typography.headlineMedium,
        )

        when (state.step) {
            LoginStep.EMAIL -> {
                Text(
                    text = stringResource(R.string.login_subtitle),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedTextField(
                    value = state.email,
                    onValueChange = onEmailChange,
                    label = { Text(stringResource(R.string.login_email)) },
                    singleLine = true,
                    isError = state.errorMessage != null,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            LoginStep.CODE -> {
                Text(
                    text = stringResource(R.string.login_code_sent, state.email),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedTextField(
                    value = state.code,
                    onValueChange = onCodeChange,
                    label = { Text(stringResource(R.string.login_code)) },
                    singleLine = true,
                    isError = state.errorMessage != null,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }

        state.errorMessage?.let { message ->
            Text(
                text = stringResource(message),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.error,
            )
        }

        // Debug builds only — null in release, so nothing leaks to users.
        state.debugDetail?.let { detail ->
            Text(
                text = detail,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        // The single filled emphasis on this screen.
        Button(
            onClick = onSubmit,
            enabled = !state.isSubmitting && when (state.step) {
                LoginStep.EMAIL -> state.email.isNotBlank()
                LoginStep.CODE -> state.code.length == CODE_LENGTH
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(
                stringResource(
                    when (state.step) {
                        LoginStep.EMAIL -> R.string.login_submit
                        LoginStep.CODE -> R.string.login_verify
                    },
                ),
            )
        }

        if (state.step == LoginStep.CODE) {
            TextButton(onClick = onEditEmail, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.login_edit_email))
            }
        }

        // Outlined, not filled: the screen already has its one filled action.
        // Only on the address step — mid-code a second way in is just noise.
        if (state.googleAvailable && state.step == LoginStep.EMAIL) {
            OutlinedButton(
                onClick = onGoogleSignIn,
                enabled = !state.isSubmitting,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(stringResource(R.string.login_google))
            }
        }

        // Quiet, and at the foot of the screen on purpose. Almost nobody needs
        // it — but a self-hosted club cannot reach their own server without it,
        // and telling them to build their own APK to change a hostname is not an
        // answer. The address itself is shown so it is obvious which server a
        // failed sign-in was talking to.
        TextButton(
            onClick = { choosingServer = true },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(
                text = "${stringResource(R.string.login_server_change)} · ${state.serverUrl}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun ServerDialog(
    current: String,
    onDismiss: () -> Unit,
    onConfirm: (String) -> Unit,
    onReset: () -> Unit,
) {
    var value by remember(current) { mutableStateOf(current) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.login_server_title)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(UnefySpacing.sm)) {
                OutlinedTextField(
                    value = value,
                    onValueChange = { value = it },
                    label = { Text(stringResource(R.string.login_server_label)) },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                    modifier = Modifier.fillMaxWidth(),
                )
                Text(
                    text = stringResource(R.string.login_server_hint),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onConfirm(value) }) {
                Text(stringResource(R.string.login_server_save))
            }
        },
        dismissButton = {
            Row {
                TextButton(onClick = onReset) {
                    Text(stringResource(R.string.login_server_reset))
                }
                TextButton(onClick = onDismiss) {
                    Text(stringResource(R.string.login_server_cancel))
                }
            }
        },
    )
}

@Preview
@Composable
private fun LoginPreview() {
    UnefyTheme {
        LoginScreen(
            state = LoginUiState(
                email = "andreas@widmer.im",
                serverUrl = "https://api.unefy.app",
                googleAvailable = true,
            ),
        )
    }
}

@Preview
@Composable
private fun LoginCodePreview() {
    UnefyTheme {
        LoginScreen(
            state = LoginUiState(
                email = "andreas@widmer.im",
                step = LoginStep.CODE,
                code = "123",
                serverUrl = "https://api.unefy.app",
            ),
        )
    }
}
