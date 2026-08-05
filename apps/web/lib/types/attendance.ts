/** A window during which members can be checked in — the appointment itself. */
export type AttendanceSession = {
  id: string
  title: string
  division_id: string | null
  event_id: string | null
  location: string | null
  opens_at: string
  closes_at: string
  /** "open" | "closed". A closed session is frozen and accepts no changes. */
  status: string
  supervisor_member_id: string | null
  supervisor_name: string | null
  closed_at: string | null
  closed_by: string | null
  record_count: number
  created_at: string
  updated_at: string
}

/** One member's attendance at one session. */
export type AttendanceRecord = {
  id: string
  session_id: string
  member_id: string
  member_name: string | null
  member_number: string | null
  occurred_on: string
  checked_in_at: string
  checked_out_at: string | null
  /** Only "manual" exists so far; the rest of the scale is not built yet. */
  method: string
  /** "low" | "medium" | "high" — follows from the method, never claimed. */
  assurance: string
  verified_by_user_id: string | null
  note: string | null
  created_at: string
}

export type AttendanceSessionDetail = AttendanceSession & {
  records: AttendanceRecord[]
}

/** A record seen from the member's side — the session is the context. */
export type MemberAttendanceRecord = AttendanceRecord & {
  session_title: string | null
  session_location: string | null
}

/** A field-level before/after, as stored in the audit entry. */
export type AuditChange = { from: unknown; to: unknown }

export type AuditEntry = {
  id: string
  action: string
  target_type: string
  target_id: string
  actor_user_id: string | null
  actor_name: string | null
  changes: Record<string, AuditChange | unknown> | null
  reason: string | null
  created_at: string
}
