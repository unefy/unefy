"use server"

import { revalidatePath } from "next/cache"
import { z } from "zod"

import { apiCall, ApiError } from "@/lib/api"
import type { ActionResult } from "@/actions/members"
import type { ConsentKind } from "@/lib/types/consent"

function toError<T>(error: unknown): ActionResult<T> {
  if (error instanceof ApiError) {
    if (error.status === 403) return { success: false, error: "forbidden" }
    if (error.status === 404) return { success: false, error: "notFound" }
    if (error.status === 422) return { success: false, error: "validation" }
    return { success: false, error: "unknown" }
  }
  return { success: false, error: "unreachable" }
}

const KINDS = ["photos", "newsletter", "directory"] as const

/**
 * Records the caller's own answer. Granting and withdrawing are one call —
 * a withdrawal that is harder than the consent was is not a valid withdrawal.
 */
export async function recordOwnConsentAction(
  kind: ConsentKind,
  granted: boolean
): Promise<ActionResult> {
  if (!z.enum(KINDS).safeParse(kind).success) {
    return { success: false, error: "validation" }
  }

  try {
    await apiCall("/api/v1/members/me/consents", {
      method: "POST",
      body: JSON.stringify({ kind, granted }),
    })
    revalidatePath("/my/consents")
    return { success: true }
  } catch (error) {
    return toError(error)
  }
}

/** Records an answer the club received on paper or by phone. */
export async function recordMemberConsentAction(
  memberId: string,
  kind: ConsentKind,
  granted: boolean,
  options: { recordedAt?: string; note?: string } = {}
): Promise<ActionResult> {
  if (!z.string().uuid().safeParse(memberId).success) {
    return { success: false, error: "validation" }
  }
  if (!z.enum(KINDS).safeParse(kind).success) {
    return { success: false, error: "validation" }
  }

  try {
    await apiCall(`/api/v1/members/${memberId}/consents`, {
      method: "POST",
      body: JSON.stringify({
        kind,
        granted,
        recorded_at: options.recordedAt?.trim()
          ? // A date without a time is midnight in the club's day, which is
            // what somebody entering "signed on the 3rd" means.
            new Date(`${options.recordedAt}T12:00:00`).toISOString()
          : null,
        note: options.note?.trim() || null,
      }),
    })
    revalidatePath(`/members/${memberId}/consents`)
    // The directory hides members who refused, so it changes with this.
    revalidatePath("/members")
    return { success: true }
  } catch (error) {
    return toError(error)
  }
}
