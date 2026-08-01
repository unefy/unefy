import { apiCall, apiList } from "@/lib/api"
import { getClub } from "@/lib/club"
import { FALLBACK_TIME_ZONE } from "@/lib/time"
import type {
  AttendanceSession,
  AttendanceSessionDetail,
  AuditEntry,
} from "@/lib/types/attendance"

/**
 * Server-side readers for attendance.
 *
 * Tenant scoping happens in the backend from the session — nothing here passes
 * a tenant id, so a caller cannot reach another club's data by construction.
 */

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ""
}

/** The list sorts and filters on the client, so it asks for one full page. */
export const SESSION_PAGE_SIZE = 100

export async function listAttendanceSessions(
  options: { page?: number; perPage?: number; status?: string } = {}
) {
  return apiList<AttendanceSession>(
    `/api/v1/attendance/sessions${query({
      page: options.page,
      per_page: options.perPage ?? SESSION_PAGE_SIZE,
      status: options.status,
    })}`
  )
}

export async function getAttendanceSession(sessionId: string) {
  return apiCall<AttendanceSessionDetail>(
    `/api/v1/attendance/sessions/${sessionId}`
  )
}

/**
 * The session's trail plus that of every record in it, oldest first — including
 * records that were corrected away, which are the entries people look for.
 */
export async function getAttendanceSessionAudit(sessionId: string) {
  return apiCall<AuditEntry[]>(`/api/v1/attendance/sessions/${sessionId}/audit`)
}

/**
 * The club's time zone, for rendering attendance times.
 *
 * Falls back rather than failing: a missing club record must not take down the
 * attendance list, and being an hour out beats showing nothing.
 */
export async function getClubTimeZone(): Promise<string> {
  const club = await getClub().catch(() => null)
  return club?.timezone || FALLBACK_TIME_ZONE
}
