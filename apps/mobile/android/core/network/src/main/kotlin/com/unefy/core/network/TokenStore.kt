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
 * Base URL is injected rather than compiled into this module: it differs per
 * build type, per device and — since unefy is self-hostable — per installation.
 * No hardcoded URLs, see apps/mobile/CLAUDE.md.
 *
 * Resolved per request rather than captured once. The address is a setting a
 * person can change on the login screen, and the HTTP clients are singletons
 * built long before that happens; holding a `String` here meant a new server
 * only took effect after killing the app.
 */
class ApiConfig(private val resolve: () -> String) {

    constructor(baseUrl: String) : this({ baseUrl })

    val baseUrl: String get() = resolve()
}
