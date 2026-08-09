import type { AttendanceSession } from "@/lib/types/attendance"

/** The event types the backend accepts — mirrors `EVENT_TYPE_PATTERN`. */
export const EVENT_TYPE_KEYS = [
  "training",
  "meeting",
  "celebration",
  "competition",
  "other",
] as const

export type EventType = (typeof EVENT_TYPE_KEYS)[number]

/** An event as returned by `/api/v1/events`. */
export type ClubEvent = {
  id: string
  title: string
  description: string | null
  event_type: string
  location: string | null
  starts_at: string
  ends_at: string | null
  all_day: boolean
  registration_required: boolean
  registration_deadline: string | null
  max_participants: number | null
  /** "scheduled" | "cancelled". */
  status: string
  competition_id: string | null
  session_id: string | null
  competition_name: string | null
  registered_count: number
  /** Whether the caller is on the list — waitlisted counts as registered. */
  is_registered: boolean
  created_at: string
  updated_at: string
}

/** One person on an event. `status` is "registered" | "waitlisted". */
export type EventRegistration = {
  id: string
  event_id: string
  member_id: string
  member_name: string | null
  status: string
  note: string | null
  created_at: string
}

/**
 * The detail response. `attendance_sessions` arrives empty for members: the
 * backend hands the attendance side to board roles only.
 */
export type ClubEventDetail = ClubEvent & {
  registrations: EventRegistration[]
  attendance_sessions: AttendanceSession[]
}
