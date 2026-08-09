"use server"

import { revalidatePath } from "next/cache"
import { z } from "zod"

import { apiCall, ApiError } from "@/lib/api"
import {
  parseAssignmentForm,
  parseFeeTypeForm,
  parsePaymentForm,
} from "@/lib/due-schema"
import type { FeeType, MemberFeeAssignment, MyDue } from "@/lib/types/due"

export type ActionResult<T = unknown> =
  | { success: true; data?: T }
  | { success: false; error: string }

function toError<T>(error: unknown): ActionResult<T> {
  if (error instanceof ApiError) {
    if (error.status === 409) return { success: false, error: "conflict" }
    if (error.status === 403) return { success: false, error: "forbidden" }
    if (error.status === 404) return { success: false, error: "notFound" }
    // The SEPA export answers 422 for both halves of "cannot collect yet":
    // missing creditor data, or nothing eligible to collect.
    if (error.status === 422) return { success: false, error: "validation" }
    return { success: false, error: "unknown" }
  }
  return { success: false, error: "unreachable" }
}

const uuid = z.string().uuid()

function refreshDues(memberId?: string) {
  revalidatePath("/dues")
  revalidatePath("/")
  if (memberId) revalidatePath(`/members/${memberId}/dues`)
}

// --- Fee types ---

export async function createFeeTypeAction(
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<FeeType>> {
  const parsed = parseFeeTypeForm(formData)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const created = await apiCall<FeeType>("/api/v1/dues/fee-types", {
      method: "POST",
      body: JSON.stringify(parsed.data),
    })
    revalidatePath("/dues/fee-types")
    return { success: true, data: created }
  } catch (error) {
    return toError(error)
  }
}

export async function updateFeeTypeAction(
  feeTypeId: string,
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<FeeType>> {
  if (!uuid.safeParse(feeTypeId).success) {
    return { success: false, error: "validation" }
  }
  const parsed = parseFeeTypeForm(formData)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const updated = await apiCall<FeeType>(
      `/api/v1/dues/fee-types/${feeTypeId}`,
      { method: "PATCH", body: JSON.stringify(parsed.data) }
    )
    revalidatePath("/dues/fee-types")
    return { success: true, data: updated }
  } catch (error) {
    return toError(error)
  }
}

/** Retiring a fee type keeps the dues already assessed from it. */
export async function setFeeTypeActiveAction(
  feeTypeId: string,
  isActive: boolean
): Promise<ActionResult<FeeType>> {
  if (!uuid.safeParse(feeTypeId).success) {
    return { success: false, error: "validation" }
  }
  try {
    const updated = await apiCall<FeeType>(
      `/api/v1/dues/fee-types/${feeTypeId}`,
      { method: "PATCH", body: JSON.stringify({ is_active: isActive }) }
    )
    revalidatePath("/dues/fee-types")
    return { success: true, data: updated }
  } catch (error) {
    return toError(error)
  }
}

export async function deleteFeeTypeAction(
  feeTypeId: string
): Promise<ActionResult> {
  if (!uuid.safeParse(feeTypeId).success) {
    return { success: false, error: "validation" }
  }
  try {
    await apiCall(`/api/v1/dues/fee-types/${feeTypeId}`, { method: "DELETE" })
  } catch (error) {
    return toError(error)
  }
  revalidatePath("/dues/fee-types")
  return { success: true }
}

// --- Assignments ---

export async function createAssignmentAction(
  memberId: string,
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<MemberFeeAssignment>> {
  const parsed = parseAssignmentForm(formData)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const created = await apiCall<MemberFeeAssignment>(
      "/api/v1/dues/assignments",
      { method: "POST", body: JSON.stringify(parsed.data) }
    )
    refreshDues(memberId)
    return { success: true, data: created }
  } catch (error) {
    return toError(error)
  }
}

export async function deleteAssignmentAction(
  memberId: string,
  assignmentId: string
): Promise<ActionResult> {
  if (!uuid.safeParse(assignmentId).success) {
    return { success: false, error: "validation" }
  }
  try {
    await apiCall(`/api/v1/dues/assignments/${assignmentId}`, {
      method: "DELETE",
    })
  } catch (error) {
    return toError(error)
  }
  refreshDues(memberId)
  return { success: true }
}

// --- Dues ---

/**
 * Runs the assessment for a year.
 *
 * Idempotent in the backend: a second run skips what already exists, so a
 * treasurer who is unsure whether the run went through can simply repeat it.
 */
export async function generateDuesAction(
  year: number
): Promise<ActionResult<{ created: number }>> {
  const parsed = z.number().int().min(2000).max(2100).safeParse(year)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const result = await apiCall<{ created: number }>("/api/v1/dues/generate", {
      method: "POST",
      body: JSON.stringify({ year: parsed.data }),
    })
    refreshDues()
    return { success: true, data: result }
  } catch (error) {
    return toError(error)
  }
}

export async function payDueAction(
  dueId: string,
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<MyDue>> {
  if (!uuid.safeParse(dueId).success) {
    return { success: false, error: "validation" }
  }
  const parsed = parsePaymentForm(formData)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const due = await apiCall<MyDue>(`/api/v1/dues/${dueId}/pay`, {
      method: "POST",
      body: JSON.stringify(parsed.data),
    })
    refreshDues(due.member_id)
    return { success: true, data: due }
  } catch (error) {
    return toError(error)
  }
}

export async function cancelDueAction(
  dueId: string
): Promise<ActionResult<MyDue>> {
  if (!uuid.safeParse(dueId).success) {
    return { success: false, error: "validation" }
  }
  try {
    const due = await apiCall<MyDue>(`/api/v1/dues/${dueId}/cancel`, {
      method: "POST",
    })
    refreshDues(due.member_id)
    return { success: true, data: due }
  } catch (error) {
    return toError(error)
  }
}

/** Undo for both of the above — a payment booked on the wrong person. */
export async function reopenDueAction(
  dueId: string
): Promise<ActionResult<MyDue>> {
  if (!uuid.safeParse(dueId).success) {
    return { success: false, error: "validation" }
  }
  try {
    const due = await apiCall<MyDue>(`/api/v1/dues/${dueId}/reopen`, {
      method: "POST",
    })
    refreshDues(due.member_id)
    return { success: true, data: due }
  } catch (error) {
    return toError(error)
  }
}
