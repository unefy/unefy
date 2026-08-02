package com.unefy.core.model

/**
 * The token pair returned by the backend's mobile auth endpoints, plus the
 * absolute expiry the app derives from `access_expires_in`.
 */
data class AuthTokens(
    val accessToken: String,
    val refreshToken: String,
    val accessExpiresAtEpochSeconds: Long,
)

/** Signed-in user, as returned alongside the token pair. */
data class AuthUser(
    val id: String,
    val name: String?,
    val email: String,
    val locale: String?,
)

/**
 * The club the session is scoped to. Every request is tenant-scoped on the
 * backend, so this is not decoration — it tells the user which club they are
 * looking at when their account belongs to several.
 */
data class Tenant(
    val id: String,
    val name: String,
    val slug: String?,
    val shortName: String?,
)

data class Session(
    val user: AuthUser,
    val tenant: Tenant,
    val role: String,
)
