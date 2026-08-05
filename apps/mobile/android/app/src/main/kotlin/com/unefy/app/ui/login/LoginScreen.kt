package com.unefy.app.ui.login

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
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
    LoginScreen(
        state = state,
        onEmailChange = viewModel::onEmailChange,
        onCodeChange = viewModel::onCodeChange,
        onEditEmail = viewModel::editEmail,
        onSubmit = viewModel::submit,
    )
}

@Composable
fun LoginScreen(
    state: LoginUiState,
    onEmailChange: (String) -> Unit = {},
    onCodeChange: (String) -> Unit = {},
    onEditEmail: () -> Unit = {},
    onSubmit: () -> Unit = {},
) {
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
    }
}

@Preview
@Composable
private fun LoginPreview() {
    UnefyTheme { LoginScreen(state = LoginUiState(email = "andreas@widmer.im")) }
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
            ),
        )
    }
}
