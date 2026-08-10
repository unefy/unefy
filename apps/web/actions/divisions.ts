"use server"

import { revalidatePath } from "next/cache"
import { z } from "zod"

import { apiCall, ApiError } from "@/lib/api"
import type { ClubDivision } from "@/lib/types/functions"

export type ActionResult<T = unknown> =
  | { success: true; data?: T }
  | { success: false; error: string }

function toError<T>(error: unknown): ActionResult<T> {
  if (error instanceof ApiError) {
    // The backend distinguishes three refusals here, and each one has
    // something different to tell the operator.
    if (error.code === "DIVISION_EXISTS") {
      return { success: false, error: "nameTaken" }
    }
    if (error.code === "DIVISION_PRIMARY") {
      return { success: false, error: "primary" }
    }
    if (error.code === "DIVISION_IN_USE") {
      return { success: false, error: "inUse" }
    }
    if (error.status === 403) return { success: false, error: "forbidden" }
    if (error.status === 404) return { success: false, error: "notFound" }
    if (error.status === 422) return { success: false, error: "validation" }
    return { success: false, error: "unknown" }
  }
  return { success: false, error: "unreachable" }
}

const uuid = z.string().uuid()

const divisionSchema = z.object({
  name: z.string().trim().min(1).max(255),
  // An empty select means "no sport yet", which the API spells as null.
  sport_id: z
    .string()
    .optional()
    .transform((value) => (value?.trim() ? value : null))
    .refine((value) => value === null || uuid.safeParse(value).success, {
      message: "invalid sport",
    }),
})

function refresh() {
  revalidatePath("/settings/divisions")
  // Division names sit in pickers all over the app.
  revalidatePath("/", "layout")
}

export async function createDivisionAction(
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<ClubDivision>> {
  const parsed = divisionSchema.safeParse(Object.fromEntries(formData))
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const created = await apiCall<ClubDivision>("/api/v1/club/divisions", {
      method: "POST",
      body: JSON.stringify(parsed.data),
    })
    refresh()
    return { success: true, data: created }
  } catch (error) {
    return toError(error)
  }
}

export async function updateDivisionAction(
  divisionId: string,
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<ClubDivision>> {
  if (!uuid.safeParse(divisionId).success) {
    return { success: false, error: "validation" }
  }
  const parsed = divisionSchema.safeParse(Object.fromEntries(formData))
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const updated = await apiCall<ClubDivision>(
      `/api/v1/club/divisions/${divisionId}`,
      { method: "PATCH", body: JSON.stringify(parsed.data) }
    )
    refresh()
    return { success: true, data: updated }
  } catch (error) {
    return toError(error)
  }
}

export async function deleteDivisionAction(
  divisionId: string
): Promise<ActionResult> {
  if (!uuid.safeParse(divisionId).success) {
    return { success: false, error: "validation" }
  }
  try {
    await apiCall(`/api/v1/club/divisions/${divisionId}`, { method: "DELETE" })
  } catch (error) {
    return toError(error)
  }
  refresh()
  return { success: true }
}
