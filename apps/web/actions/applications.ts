"use server"

import { revalidatePath } from "next/cache"
import { z } from "zod"

import { API_BASE, apiCall, ApiError } from "@/lib/api"
import { parseApplicationForm } from "@/lib/application-schema"
import type { ActionResult } from "@/actions/members"
import type { Member } from "@/lib/types/member"

function toError<T>(error: unknown): ActionResult<T> {
  if (error instanceof ApiError) {
    if (error.status === 409) return { success: false, error: "conflict" }
    if (error.status === 403) return { success: false, error: "forbidden" }
    if (error.status === 404) return { success: false, error: "notFound" }
    if (error.status === 422) return { success: false, error: "validation" }
    return { success: false, error: "unknown" }
  }
  return { success: false, error: "unreachable" }
}

/**
 * Submits the public join form.
 *
 * Does not use `apiCall`: there is no session to forward, and forwarding one
 * would be wrong even if there were — an applicant filling in a form on a
 * club computer must not submit as whoever is signed in on it.
 */
export async function submitApplicationAction(
  slug: string,
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult> {
  const parsed = parseApplicationForm(formData)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const response = await fetch(
      `${API_BASE}/join/${encodeURIComponent(slug)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed.data),
        cache: "no-store",
      }
    )
    if (response.status === 429) return { success: false, error: "rateLimited" }
    if (response.status === 422) return { success: false, error: "validation" }
    if (response.status === 404) return { success: false, error: "notFound" }
    if (!response.ok) return { success: false, error: "unknown" }
    return { success: true }
  } catch {
    return { success: false, error: "unreachable" }
  }
}

export async function acceptApplicationAction(
  applicationId: string
): Promise<ActionResult<Member>> {
  if (!z.string().uuid().safeParse(applicationId).success) {
    return { success: false, error: "validation" }
  }

  try {
    const member = await apiCall<Member>(
      `/api/v1/applications/${applicationId}/accept`,
      { method: "POST" }
    )
    revalidatePath("/applications")
    revalidatePath(`/applications/${applicationId}`)
    // The member list gained a row — a stale cache there would make the
    // acceptance look like it did not happen.
    revalidatePath("/members")
    return { success: true, data: member }
  } catch (error) {
    return toError(error)
  }
}

export async function rejectApplicationAction(
  applicationId: string,
  note: string
): Promise<ActionResult> {
  if (!z.string().uuid().safeParse(applicationId).success) {
    return { success: false, error: "validation" }
  }

  try {
    await apiCall(`/api/v1/applications/${applicationId}/reject`, {
      method: "POST",
      body: JSON.stringify({ note: note.trim() || null }),
    })
    revalidatePath("/applications")
    revalidatePath(`/applications/${applicationId}`)
    return { success: true }
  } catch (error) {
    return toError(error)
  }
}
