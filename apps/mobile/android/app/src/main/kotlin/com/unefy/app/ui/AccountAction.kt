package com.unefy.app.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.unefy.app.R
import com.unefy.core.auth.TenantOption
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.theme.UnefySpacing

/**
 * The account, top right, on every screen.
 *
 * Modelled on Gmail and Play: the avatar is a persistent anchor rather than an
 * overflow menu hidden on one screen. Before this it lived only on the profile,
 * which meant a plain member could reach the member list of destinations but not
 * a sign-out.
 */
@Composable
fun accountActions(
    email: String?,
    displayName: String?,
    tenants: List<TenantOption> = emptyList(),
    onOpenMenu: () -> Unit = {},
    onSwitchTenant: (String) -> Unit = {},
    onSignOut: () -> Unit,
): @Composable RowScope.() -> Unit = {
    var expanded by remember { mutableStateOf(false) }

    Box {
        Surface(
            shape = CircleShape,
            color = MaterialTheme.colorScheme.surfaceContainerHighest,
            modifier = Modifier
                .size(AVATAR_SIZE)
                .clip(CircleShape)
                .clickable {
                    expanded = true
                    // The club list is fetched when the menu opens, not per
                    // screen — most accounts belong to one club and never
                    // need it.
                    onOpenMenu()
                },
        ) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(
                    text = initialsOf(displayName, email),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                )
            }
        }

        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            // The account's clubs, current one ticked. Only with a choice: a
            // single-club account gets a menu that is just the sign-out, and
            // the email deliberately does not appear here — the avatar's
            // initials already say whose menu this is.
            if (tenants.size > 1) {
                Text(
                    text = stringResource(R.string.account_switch_club),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(
                        horizontal = UnefySpacing.md,
                        vertical = UnefySpacing.sm,
                    ),
                )
                tenants.forEach { tenant ->
                    DropdownMenuItem(
                        text = { Text(tenant.name) },
                        onClick = {
                            expanded = false
                            if (!tenant.isCurrent) onSwitchTenant(tenant.id)
                        },
                        trailingIcon = {
                            if (tenant.isCurrent) {
                                Icon(
                                    painter = painterResource(DesignR.drawable.ic_check),
                                    contentDescription =
                                        stringResource(R.string.account_current_club),
                                )
                            }
                        },
                    )
                }
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            }
            DropdownMenuItem(
                text = { Text(stringResource(R.string.account_sign_out)) },
                onClick = {
                    expanded = false
                    onSignOut()
                },
                leadingIcon = {
                    Icon(
                        painter = painterResource(DesignR.drawable.ic_logout),
                        contentDescription = null,
                    )
                },
            )
        }
    }
}

/**
 * Initials from the name, falling back to the email so the circle is never blank.
 *
 * The domain is cut first: accounts created by the dev login carry the address
 * as their name, and splitting "testine@example.com" on dots produced "TC".
 */
private fun initialsOf(displayName: String?, email: String?): String {
    val source = displayName?.takeIf { it.isNotBlank() } ?: email
    val local = source?.substringBefore('@')
    val initials = local
        ?.split(' ', '.', '-', '_')
        ?.filter { it.isNotBlank() }
        ?.take(2)
        ?.mapNotNull { it.firstOrNull()?.uppercase() }
        ?.joinToString(separator = "")
    return initials?.takeIf { it.isNotBlank() } ?: "?"
}

private val AVATAR_SIZE = 36.dp
