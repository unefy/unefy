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

    const val COMPETITIONS = "/api/v1/competitions"

    const val CLUB = "/api/v1/club"

    /**
     * Delta-sync. Deliberately separate from the list endpoints: `/members`
     * carries filters, offset paging and a `status_counts` aggregate, and these
     * carry a keyset cursor and tombstones. See backend/app/api/v1/sync.py.
     */
    const val SYNC = "/api/v1/sync"

    /** The collection name is the path segment, and also the SSE `entity` value. */
    fun sync(collection: String): String = "$SYNC/$collection"

    /** The change stream. A doorbell: it says something changed, not what. */
    const val STREAM = "/api/v1/stream"

    /** Where a phone asks to be woken (FCM). Registering is an upsert by token. */
    const val PUSH_DEVICES = "/api/v1/push/devices"

    /** A POST, not a DELETE: the token must not appear in a URL or access log. */
    const val PUSH_DEVICES_UNREGISTER = "$PUSH_DEVICES/unregister"

    const val ATTENDANCE = "/api/v1/attendance"
    const val ATTENDANCE_SESSIONS = "$ATTENDANCE/sessions"

    /** The 24h seed the app computes its rotating check-in code from. */
    const val ATTENDANCE_ME_SEED = "$ATTENDANCE/me/seed"
    const val ATTENDANCE_ME_RECORDS = "$ATTENDANCE/me/records"

    /** Check-in from a scanned code, as opposed to a supervisor ticking a box. */
    fun attendanceScan(sessionId: String): String = "$ATTENDANCE_SESSIONS/$sessionId/scan"

    /** The supervisor ticking a box, as opposed to scanning a code. */
    fun attendanceCheckIn(sessionId: String): String = "$ATTENDANCE_SESSIONS/$sessionId/check-in"

    fun attendanceRecords(sessionId: String): String = "$ATTENDANCE_SESSIONS/$sessionId/records"

    /** Soft-deletes one record. Refused once the session is closed. */
    fun attendanceRecord(recordId: String): String = "$ATTENDANCE/records/$recordId"

    fun member(id: String): String = "$MEMBERS/$id"

    /** The single event, with its registrations — what the detail screen shows. */
    fun event(id: String): String = "$EVENTS/$id"

    fun eventSelfRegistration(eventId: String): String = "$EVENTS/$eventId/registrations/me"

    /** Board-level: registering someone else, as opposed to `…/me`. */
    fun eventRegistrations(eventId: String): String = "$EVENTS/$eventId/registrations"

    fun eventRegistration(eventId: String, registrationId: String): String =
        "$EVENTS/$eventId/registrations/$registrationId"

    /** The live ranking — a server aggregate, not a synced collection. */
    fun competitionScoreboard(competitionId: String): String =
        "$COMPETITIONS/$competitionId/scoreboard"
}
