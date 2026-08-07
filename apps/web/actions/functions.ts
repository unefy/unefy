"use server"

import { revalidatePath } from "next/cache"
import { z } from "zod"

import { apiCall, ApiError } from "@/lib/api"
import type { ClubFunction, MemberFunction } from "@/lib/types/functions"

export type ActionResult<T = unknown> =
  | { success: true; data?: T }
  | { success: false; error: string }

function toError<T>(error: unknown): ActionResult<T> {
  if (error instanceof ApiError) {
    if (error.status === 403) return { success: false, error: "forbidden" }
    if (error.status === 404) return { success: false, error: "notFound" }
    if (error.status === 409) return { success: false, error: "conflict" }
    if (error.status === 422) return { success: false, error: "validation" }
    return { success: false, error: "unknown" }
  }
  return { success: false, error: "unreachable" }
}

const functionSchema = z.object({
  name: z.string().trim().min(1).max(255),
  level: z.enum(["club", "division"]),
  suggested_role: z.enum(["owner", "admin", "board", "member"]).nullable(),
  sort_order: z.number().int(),
  is_active: z.boolean(),
})

export async function createFunctionAction(
  input: z.infer<typeof functionSchema>
): Promise<ActionResult<ClubFunction>> {
  const parsed = functionSchema.safeParse(input)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const created = await apiCall<ClubFunction>("/api/v1/functions", {
      method: "POST",
      body: JSON.stringify(parsed.data),
    })
    revalidatePath("/settings/functions")
    return { success: true, data: created }
  } catch (error) {
    return toError(error)
  }
}

export async function updateFunctionAction(
  functionId: string,
  input: Partial<z.infer<typeof functionSchema>>
): Promise<ActionResult<ClubFunction>> {
  const parsed = functionSchema.partial().safeParse(input)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const updated = await apiCall<ClubFunction>(
      `/api/v1/functions/${functionId}`,
      { method: "PATCH", body: JSON.stringify(parsed.data) }
    )
    revalidatePath("/settings/functions")
    return { success: true, data: updated }
  } catch (error) {
    return toError(error)
  }
}

export async function deleteFunctionAction(
  functionId: string
): Promise<ActionResult> {
  try {
    await apiCall(`/api/v1/functions/${functionId}`, { method: "DELETE" })
    revalidatePath("/settings/functions")
    return { success: true }
  } catch (error) {
    return toError(error)
  }
}

const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/)

const assignmentSchema = z.object({
  function_id: z.string().uuid(),
  division_id: z.string().uuid().nullable(),
  valid_from: isoDate,
  valid_to: isoDate.nullable(),
  note: z
    .string()
    .trim()
    .max(500)
    .transform((value) => (value === "" ? null : value))
    .nullable(),
})

export async function assignMemberFunctionAction(
  memberId: string,
  input: z.infer<typeof assignmentSchema>
): Promise<ActionResult<MemberFunction>> {
  const parsed = assignmentSchema.safeParse(input)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const created = await apiCall<MemberFunction>(
      `/api/v1/members/${memberId}/functions`,
      { method: "POST", body: JSON.stringify(parsed.data) }
    )
    revalidatePath(`/members/${memberId}/functions`)
    return { success: true, data: created }
  } catch (error) {
    return toError(error)
  }
}

export async function updateMemberFunctionAction(
  memberId: string,
  assignmentId: string,
  input: Partial<z.infer<typeof assignmentSchema>>
): Promise<ActionResult<MemberFunction>> {
  const parsed = assignmentSchema
    .omit({ function_id: true })
    .partial()
    .safeParse(input)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const updated = await apiCall<MemberFunction>(
      `/api/v1/members/${memberId}/functions/${assignmentId}`,
      { method: "PATCH", body: JSON.stringify(parsed.data) }
    )
    revalidatePath(`/members/${memberId}/functions`)
    return { success: true, data: updated }
  } catch (error) {
    return toError(error)
  }
}

export async function deleteMemberFunctionAction(
  memberId: string,
  assignmentId: string
): Promise<ActionResult> {
  try {
    await apiCall(`/api/v1/members/${memberId}/functions/${assignmentId}`, {
      method: "DELETE",
    })
    revalidatePath(`/members/${memberId}/functions`)
    return { success: true }
  } catch (error) {
    return toError(error)
  }
}
