package com.unefy.core.network

import com.unefy.core.model.AuthTokens

/**
 * Declared here, implemented in `core:auth`.
 *
 * This is what keeps the two modules acyclic: the network layer needs tokens to
 * sign requests and a way to refresh them, but it must not know how they are
 * encrypted or where they are stored. `core:auth` depends on `core:network`,
 * never the other way round.
 */
interface TokenStore {
    /** The current pair, or null when signed out. */
    suspend fun current(): AuthTokens?

    /**
     * Called by the Ktor Auth plugin after a 401. Returns the new pair, or null
     * if the refresh token is also dead — in which case the session is over.
     */
    suspend fun refresh(): AuthTokens?
}

/**
 * Base URL is injected rather than compiled into this module: it differs
 * per build type and per device (an emulator reaches the host at 10.0.2.2, a
 * phone needs the machine's LAN address). No hardcoded URLs — see
 * apps/mobile/CLAUDE.md.
 */
data class ApiConfig(
    val baseUrl: String,
)
