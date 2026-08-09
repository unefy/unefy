"use server"

import { revalidatePath } from "next/cache"
import { z } from "zod"

import { apiCall, ApiError } from "@/lib/api"
import { parseEventForm } from "@/lib/event-schema"
import type { AttendanceSession } from "@/lib/types/attendance"
import type { ClubEvent, EventRegistration } from "@/lib/types/event"

export type ActionResult<T = unknown> =
  | { success: true; data?: T }
  | { success: false; error: string }

function toError<T>(error: unknown): ActionResult<T> {
  if (error instanceof ApiError) {
    // 409 here means the event is full or the member is already on it — the
    // two cases the UI has something useful to say about.
    if (error.status === 409) return { success: false, error: "conflict" }
    if (error.status === 403) return { success: false, error: "forbidden" }
    if (error.status === 404) return { success: false, error: "notFound" }
    if (error.status === 422) return { success: false, error: "validation" }
    return { success: false, error: "unknown" }
  }
  return { success: false, error: "unreachable" }
}

const uuid = z.string().uuid()

function refreshEvent(eventId?: string) {
  revalidatePath("/events")
  if (eventId) revalidatePath(`/events/${eventId}`)
}

export async function createEventAction(
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<ClubEvent>> {
  const parsed = parseEventForm(formData)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const created = await apiCall<ClubEvent>("/api/v1/events", {
      method: "POST",
      body: JSON.stringify(parsed.data),
    })
    refreshEvent(created.id)
    return { success: true, data: created }
  } catch (error) {
    return toError(error)
  }
}

export async function updateEventAction(
  eventId: string,
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<ClubEvent>> {
  if (!uuid.safeParse(eventId).success) {
    return { success: false, error: "validation" }
  }
  const parsed = parseEventForm(formData)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const updated = await apiCall<ClubEvent>(`/api/v1/events/${eventId}`, {
      method: "PATCH",
      body: JSON.stringify(parsed.data),
    })
    refreshEvent(eventId)
    return { success: true, data: updated }
  } catch (error) {
    return toError(error)
  }
}

/** Cancelling keeps the event and its registrations; deleting does not. */
export async function cancelEventAction(
  eventId: string
): Promise<ActionResult<ClubEvent>> {
  if (!uuid.safeParse(eventId).success) {
    return { success: false, error: "validation" }
  }
  try {
    const updated = await apiCall<ClubEvent>(`/api/v1/events/${eventId}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "cancelled" }),
    })
    refreshEvent(eventId)
    return { success: true, data: updated }
  } catch (error) {
    return toError(error)
  }
}

export async function deleteEventAction(
  eventId: string
): Promise<ActionResult> {
  if (!uuid.safeParse(eventId).success) {
    return { success: false, error: "validation" }
  }
  try {
    await apiCall(`/api/v1/events/${eventId}`, { method: "DELETE" })
  } catch (error) {
    return toError(error)
  }
  refreshEvent()
  return { success: true }
}

/** Registers the caller. The member id comes from the session, never the form. */
export async function registerSelfAction(
  eventId: string
): Promise<ActionResult<EventRegistration>> {
  if (!uuid.safeParse(eventId).success) {
    return { success: false, error: "validation" }
  }
  try {
    const registration = await apiCall<EventRegistration>(
      `/api/v1/events/${eventId}/registrations/me`,
      { method: "POST" }
    )
    refreshEvent(eventId)
    return { success: true, data: registration }
  } catch (error) {
    return toError(error)
  }
}

export async function unregisterSelfAction(
  eventId: string
): Promise<ActionResult> {
  if (!uuid.safeParse(eventId).success) {
    return { success: false, error: "validation" }
  }
  try {
    await apiCall(`/api/v1/events/${eventId}/registrations/me`, {
      method: "DELETE",
    })
  } catch (error) {
    return toError(error)
  }
  refreshEvent(eventId)
  return { success: true }
}

/** Board-level: put someone else on the event. */
export async function registerMemberAction(
  eventId: string,
  memberId: string
): Promise<ActionResult<EventRegistration>> {
  if (!uuid.safeParse(eventId).success || !uuid.safeParse(memberId).success) {
    return { success: false, error: "validation" }
  }
  try {
    const registration = await apiCall<EventRegistration>(
      `/api/v1/events/${eventId}/registrations`,
      { method: "POST", body: JSON.stringify({ member_id: memberId }) }
    )
    refreshEvent(eventId)
    return { success: true, data: registration }
  } catch (error) {
    return toError(error)
  }
}

/** Removing a registration promotes the first waitlisted member server-side. */
export async function removeRegistrationAction(
  eventId: string,
  registrationId: string
): Promise<ActionResult> {
  if (
    !uuid.safeParse(eventId).success ||
    !uuid.safeParse(registrationId).success
  ) {
    return { success: false, error: "validation" }
  }
  try {
    await apiCall(
      `/api/v1/events/${eventId}/registrations/${registrationId}`,
      { method: "DELETE" }
    )
  } catch (error) {
    return toError(error)
  }
  refreshEvent(eventId)
  return { success: true }
}

/**
 * Opens the event's attendance session, or returns the one already open.
 *
 * Idempotent in the backend, so the button may be pressed twice without
 * producing a second evening.
 */
export async function startAttendanceAction(
  eventId: string
): Promise<ActionResult<AttendanceSession>> {
  if (!uuid.safeParse(eventId).success) {
    return { success: false, error: "validation" }
  }
  try {
    const session = await apiCall<AttendanceSession>(
      `/api/v1/events/${eventId}/attendance-session`,
      { method: "POST" }
    )
    refreshEvent(eventId)
    revalidatePath("/attendance")
    return { success: true, data: session }
  } catch (error) {
    return toError(error)
  }
}
