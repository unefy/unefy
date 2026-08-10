import { apiCall, apiList, collectPages } from "@/lib/api"
import { getClub } from "@/lib/club"
import { FALLBACK_TIME_ZONE } from "@/lib/time"
import type {
  AttendanceSession,
  AttendanceSessionDetail,
  AuditEntry,
  MemberAttendanceRecord,
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

/**
 * Every session, across pages. Same reason as the member list: the table
 * filters over what it was handed, and an evening from March must not fall out
 * of the list because eighty were held since.
 */
export async function listAllAttendanceSessions(status?: string) {
  return collectPages<AttendanceSession>((page) =>
    apiList<AttendanceSession>(
      `/api/v1/attendance/sessions${query({
        page,
        per_page: SESSION_PAGE_SIZE,
        status,
      })}`
    )
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
/** One member's attendance history, board view. */
export async function listMemberAttendance(memberId: string, page = 1) {
  return apiList<MemberAttendanceRecord>(
    `/api/v1/members/${memberId}/attendance?page=${page}&per_page=25`
  )
}

/**
 * The caller's own attendance, club evenings and self-kept days alike.
 *
 * Collected across pages: a member with two years of range days has more than
 * one page of them, and a history that silently stops is worse than none.
 */
export async function listOwnAttendance() {
  return collectPages<MemberAttendanceRecord>((page) =>
    apiList<MemberAttendanceRecord>(
      `/api/v1/attendance/me/records?page=${page}&per_page=100`
    )
  )
}

export async function getClubTimeZone(): Promise<string> {
  const club = await getClub().catch(() => null)
  return club?.timezone || FALLBACK_TIME_ZONE
}
