"use server"

import { revalidatePath } from "next/cache"
import { z } from "zod"

import { apiCall, ApiError } from "@/lib/api"
import { parseMemberForm } from "@/lib/member-schema"
import type { Member } from "@/lib/types/member"

export type ActionResult<T = unknown> =
  { success: true; data?: T } | { success: false; error: string }

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

export async function createMemberAction(
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<Member>> {
  const parsed = parseMemberForm(formData)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    // `left_at` is meaningless on a new record and the backend has no field
    // for it on create.
    const payload = { ...parsed.data, left_at: undefined }
    delete payload.left_at
    const member = await apiCall<Member>("/api/v1/members", {
      method: "POST",
      body: JSON.stringify(payload),
    })
    revalidatePath("/members")
    return { success: true, data: member }
  } catch (error) {
    return toError(error)
  }
}

export async function updateMemberAction(
  memberId: string,
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<Member>> {
  if (!z.string().uuid().safeParse(memberId).success) {
    return { success: false, error: "validation" }
  }
  const parsed = parseMemberForm(formData)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const member = await apiCall<Member>(`/api/v1/members/${memberId}`, {
      method: "PATCH",
      body: JSON.stringify(parsed.data),
    })
    revalidatePath("/members")
    revalidatePath(`/members/${memberId}`)
    return { success: true, data: member }
  } catch (error) {
    return toError(error)
  }
}

export async function deleteMemberAction(
  memberId: string
): Promise<ActionResult> {
  if (!z.string().uuid().safeParse(memberId).success) {
    return { success: false, error: "validation" }
  }

  try {
    await apiCall(`/api/v1/members/${memberId}`, { method: "DELETE" })
  } catch (error) {
    return toError(error)
  }

  revalidatePath("/members")
  return { success: true }
}
