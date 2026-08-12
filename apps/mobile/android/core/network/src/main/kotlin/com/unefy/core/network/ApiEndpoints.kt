package com.unefy.core.network

/**
 * Typed endpoint paths. Hand-maintained against the FastAPI routes — see the
 * shared API contract note in apps/mobile/CLAUDE.md.
 */
object ApiEndpoints {
    const val AUTH_PREFIX = "/api/v1/auth"

    const val AUTH_DEV_LOGIN = "$AUTH_PREFIX/mobile/dev/login"
    const val AUTH_MAGIC_REQUEST = "$AUTH_PREFIX/mobile/magic-link/request"
    const val AUTH_MAGIC_VERIFY = "$AUTH_PREFIX/mobile/magic-link/verify"
    const val AUTH_GOOGLE_NONCE = "$AUTH_PREFIX/mobile/oauth/google/nonce"
    const val AUTH_GOOGLE_SIGN_IN = "$AUTH_PREFIX/mobile/oauth/google"
    const val AUTH_REFRESH = "$AUTH_PREFIX/mobile/refresh"
    const val AUTH_LOGOUT = "$AUTH_PREFIX/mobile/logout"
    const val AUTH_ME = "$AUTH_PREFIX/me"

    /** Every club the caller belongs to, with the current one marked. */
    const val AUTH_TENANTS = "$AUTH_PREFIX/tenants"

    /** Re-issues the mobile token pair for another of the caller's clubs. */
    const val AUTH_SWITCH_TENANT = "$AUTH_PREFIX/mobile/switch-tenant"

    const val MEMBERS = "/api/v1/members"

    /** Self-service. The backend takes the member from the session, not the path. */
    const val MEMBERS_ME = "$MEMBERS/me"
    const val MEMBERS_DIRECTORY = "$MEMBERS/directory"

    /** The caller's own terms of office. Empty for an account with no member record. */
    const val MEMBERS_ME_FUNCTIONS = "$MEMBERS_ME/functions"

    /**
     * The caller's own consents, current state and full trail.
     *
     * The POST goes to the same path: giving and withdrawing are one call, and a
     * withdrawal that were harder to perform than the consent would not be one.
     */
    const val MEMBERS_ME_CONSENTS = "$MEMBERS_ME/consents"

    const val DUES = "/api/v1/dues"
    const val DUES_ME = "$DUES/me"
    const val DUES_SUMMARY = "$DUES/summary"

    const val EVENTS = "/api/v1/events"

    const val COMPETITIONS = "/api/v1/competitions"

    /**
     * Recording shots. Separate from the competition entry routes: this one
     * resolves its own context (a member on the range has no session to file
     * under) and lets a member record for themselves.
     */
    const val ENTRIES = "/api/v1/entries"

    /** The caller's own results. Self-scoped: no member id in the path. */
    const val MY_ENTRIES = "$ENTRIES/me"

    /** Ring geometry of the standard targets. Reference data, cached locally. */
    const val TARGET_TYPES = "/api/v1/target-types"

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

    /** The member's own external self-entries — range days the club did not run. */
    const val ATTENDANCE_ME_ENTRIES = "$ATTENDANCE/me/entries"

    fun attendanceMeEntry(recordId: String): String = "$ATTENDANCE_ME_ENTRIES/$recordId"

    /** Check-in from a scanned code, as opposed to a supervisor ticking a box. */
    fun attendanceScan(sessionId: String): String = "$ATTENDANCE_SESSIONS/$sessionId/scan"

    /** The supervisor ticking a box, as opposed to scanning a code. */
    fun attendanceCheckIn(sessionId: String): String = "$ATTENDANCE_SESSIONS/$sessionId/check-in"

    fun attendanceRecords(sessionId: String): String = "$ATTENDANCE_SESSIONS/$sessionId/records"

    /** Cuts off every check-in code a member's devices can still produce. */
    fun revokeAttendanceCodes(memberId: String): String =
        "$ATTENDANCE/members/$memberId/revoke-codes"

    /** Soft-deletes one record. Refused once the session is closed. */
    fun attendanceRecord(recordId: String): String = "$ATTENDANCE/records/$recordId"

    fun member(id: String): String = "$MEMBERS/$id"

    /** A member's federation memberships (DSB, BDS, …). Board-level, read-only. */
    fun memberFederations(id: String): String = "$MEMBERS/$id/federations"

    /** A member's terms of office, newest first, ended ones included. Board-level. */
    fun memberFunctions(id: String): String = "$MEMBERS/$id/functions"

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
