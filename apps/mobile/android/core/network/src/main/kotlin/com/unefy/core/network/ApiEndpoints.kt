package com.unefy.core.network

/**
 * Typed endpoint paths. Hand-maintained against the FastAPI routes — see the
 * shared API contract note in apps/mobile/CLAUDE.md.
 */
object ApiEndpoints {
    const val AUTH_PREFIX = "/api/v1/auth"

    const val AUTH_DEV_LOGIN = "$AUTH_PREFIX/mobile/dev/login"
    const val AUTH_REFRESH = "$AUTH_PREFIX/mobile/refresh"
    const val AUTH_LOGOUT = "$AUTH_PREFIX/mobile/logout"
    const val AUTH_ME = "$AUTH_PREFIX/me"

    const val MEMBERS = "/api/v1/members"

    /** Self-service. The backend takes the member from the session, not the path. */
    const val MEMBERS_ME = "$MEMBERS/me"
    const val MEMBERS_DIRECTORY = "$MEMBERS/directory"

    const val DUES = "/api/v1/dues"
    const val DUES_ME = "$DUES/me"
    const val DUES_SUMMARY = "$DUES/summary"

    const val EVENTS = "/api/v1/events"

    const val CLUB = "/api/v1/club"

    fun member(id: String): String = "$MEMBERS/$id"

    fun eventSelfRegistration(eventId: String): String = "$EVENTS/$eventId/registrations/me"
}
