"use server"

import { revalidatePath } from "next/cache"
import { z } from "zod"

import { apiCall, apiList, ApiError } from "@/lib/api"
import type {
  AttendanceRecord,
  AttendanceSession,
} from "@/lib/types/attendance"
import type { Member } from "@/lib/types/member"

export type ActionResult<T = unknown> =
  { success: true; data?: T } | { success: false; error: string }

function toError<T>(error: unknown): ActionResult<T> {
  if (error instanceof ApiError) {
    // 409 is the interesting one here: it almost always means the session was
    // closed, or the member is already checked in.
    if (error.status === 409) return { success: false, error: "conflict" }
    if (error.status === 403) return { success: false, error: "forbidden" }
    if (error.status === 404) return { success: false, error: "notFound" }
    if (error.status === 422) return { success: false, error: "validation" }
    return { success: false, error: "unknown" }
  }
  return { success: false, error: "unreachable" }
}

const uuid = z.string().uuid()

/** Mirrors the backend: a correction without a reason is not a correction. */
const reasonSchema = z.string().trim().min(3).max(1000)

const optionalText = z
  .string()
  .trim()
  .transform((value) => (value === "" ? null : value))
  .nullable()

const sessionSchema = z
  .object({
    title: z.string().trim().min(1).max(255),
    location: optionalText,
    opens_at: z.string().datetime({ offset: true }),
    closes_at: z.string().datetime({ offset: true }),
    supervisor_member_id: z
      .string()
      .trim()
      .transform((value) => (value === "" ? null : value))
      .nullable()
      .refine((value) => value === null || uuid.safeParse(value).success),
  })
  .refine((data) => new Date(data.closes_at) > new Date(data.opens_at), {
    message: "closes_at must be after opens_at",
  })

function refreshSession(sessionId?: string) {
  revalidatePath("/attendance")
  if (sessionId) revalidatePath(`/attendance/${sessionId}`)
}

export async function createSessionAction(
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<AttendanceSession>> {
  const parsed = sessionSchema.safeParse(Object.fromEntries(formData))
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const created = await apiCall<AttendanceSession>(
      "/api/v1/attendance/sessions",
      { method: "POST", body: JSON.stringify(parsed.data) }
    )
    refreshSession(created.id)
    return { success: true, data: created }
  } catch (error) {
    return toError(error)
  }
}

export async function updateSessionAction(
  sessionId: string,
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<AttendanceSession>> {
  if (!uuid.safeParse(sessionId).success) {
    return { success: false, error: "validation" }
  }
  const parsed = sessionSchema.safeParse(Object.fromEntries(formData))
  if (!parsed.success) return { success: false, error: "validation" }

  const reason = formData.get("reason")
  try {
    const updated = await apiCall<AttendanceSession>(
      `/api/v1/attendance/sessions/${sessionId}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          ...parsed.data,
          reason: typeof reason === "string" && reason.trim() ? reason : null,
        }),
      }
    )
    refreshSession(sessionId)
    return { success: true, data: updated }
  } catch (error) {
    return toError(error)
  }
}

/**
 * Freezes the session. Irreversible — the UI must ask before calling this,
 * because there is no reopen endpoint and there is not meant to be one.
 */
export async function closeSessionAction(
  sessionId: string
): Promise<ActionResult> {
  if (!uuid.safeParse(sessionId).success) {
    return { success: false, error: "validation" }
  }
  try {
    await apiCall(`/api/v1/attendance/sessions/${sessionId}/close`, {
      method: "POST",
    })
  } catch (error) {
    return toError(error)
  }
  refreshSession(sessionId)
  return { success: true }
}

export async function deleteSessionAction(
  sessionId: string,
  reason: string
): Promise<ActionResult> {
  const parsed = reasonSchema.safeParse(reason)
  if (!uuid.safeParse(sessionId).success || !parsed.success) {
    return { success: false, error: "validation" }
  }
  try {
    await apiCall(
      `/api/v1/attendance/sessions/${sessionId}?reason=${encodeURIComponent(parsed.data)}`,
      { method: "DELETE" }
    )
  } catch (error) {
    return toError(error)
  }
  refreshSession()
  return { success: true }
}

export async function checkInAction(
  sessionId: string,
  memberId: string
): Promise<ActionResult<AttendanceRecord>> {
  if (!uuid.safeParse(sessionId).success || !uuid.safeParse(memberId).success) {
    return { success: false, error: "validation" }
  }
  try {
    const record = await apiCall<AttendanceRecord>(
      `/api/v1/attendance/sessions/${sessionId}/check-in`,
      { method: "POST", body: JSON.stringify({ member_id: memberId }) }
    )
    refreshSession(sessionId)
    return { success: true, data: record }
  } catch (error) {
    return toError(error)
  }
}

export async function checkOutAction(
  sessionId: string,
  recordId: string
): Promise<ActionResult> {
  if (!uuid.safeParse(recordId).success) {
    return { success: false, error: "validation" }
  }
  try {
    await apiCall(`/api/v1/attendance/records/${recordId}/check-out`, {
      method: "POST",
    })
  } catch (error) {
    return toError(error)
  }
  refreshSession(sessionId)
  return { success: true }
}

export async function correctRecordAction(
  sessionId: string,
  recordId: string,
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult> {
  const reason = reasonSchema.safeParse(formData.get("reason"))
  if (!uuid.safeParse(recordId).success || !reason.success) {
    return { success: false, error: "validation" }
  }
  const note = optionalText.safeParse(formData.get("note") ?? "")

  try {
    await apiCall(`/api/v1/attendance/records/${recordId}`, {
      method: "PATCH",
      body: JSON.stringify({
        note: note.success ? note.data : null,
        reason: reason.data,
      }),
    })
  } catch (error) {
    return toError(error)
  }
  refreshSession(sessionId)
  return { success: true }
}

export async function removeRecordAction(
  sessionId: string,
  recordId: string,
  reason: string
): Promise<ActionResult> {
  const parsed = reasonSchema.safeParse(reason)
  if (!uuid.safeParse(recordId).success || !parsed.success) {
    return { success: false, error: "validation" }
  }
  try {
    await apiCall(
      `/api/v1/attendance/records/${recordId}?reason=${encodeURIComponent(parsed.data)}`,
      { method: "DELETE" }
    )
  } catch (error) {
    return toError(error)
  }
  refreshSession(sessionId)
  return { success: true }
}

/**
 * Member lookup for the check-in box.
 *
 * Searches server-side rather than filtering a preloaded list: the backend caps
 * a page at 100 members, and a club with more than that must still be able to
 * find everyone.
 */
export async function searchMembersAction(
  search: string
): Promise<ActionResult<Member[]>> {
  const term = search.trim()
  if (term.length < 2) return { success: true, data: [] }

  try {
    const { data } = await apiList<Member>(
      `/api/v1/members?per_page=20&search=${encodeURIComponent(term)}`
    )
    return { success: true, data }
  } catch (error) {
    return toError(error)
  }
}
