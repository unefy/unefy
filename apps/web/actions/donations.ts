"use server"

import { revalidatePath } from "next/cache"
import { z } from "zod"

import { apiCall, ApiError } from "@/lib/api"
import type { ActionResult } from "@/actions/members"
import type { DonationReceipt } from "@/lib/types/donation"

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

const receiptSchema = z.object({
  member_id: z.string().uuid().nullable(),
  donor_name: z.string().trim().max(255).nullable(),
  donor_address: z.string().trim().max(500).nullable(),
  // Kept as a string all the way to the backend: money that goes through a
  // float on its way to a tax office is not money.
  amount: z.string().regex(/^\d+([.,]\d{1,2})?$/),
  received_on: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  kind: z.enum(["geldzuwendung", "mitgliedsbeitrag"]),
  is_expense_waiver: z.boolean(),
})

export type ReceiptInput = z.infer<typeof receiptSchema>

export async function issueReceiptAction(
  input: ReceiptInput
): Promise<ActionResult<DonationReceipt>> {
  const parsed = receiptSchema.safeParse(input)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const receipt = await apiCall<DonationReceipt>("/api/v1/donations", {
      method: "POST",
      body: JSON.stringify({
        ...parsed.data,
        amount: parsed.data.amount.replace(",", "."),
      }),
    })
    revalidatePath("/donations")
    return { success: true, data: receipt }
  } catch (error) {
    return toError(error)
  }
}

export async function revokeReceiptAction(
  receiptId: string,
  reason: string
): Promise<ActionResult> {
  if (!z.string().uuid().safeParse(receiptId).success) {
    return { success: false, error: "validation" }
  }
  if (!reason.trim()) return { success: false, error: "validation" }

  try {
    await apiCall(`/api/v1/donations/${receiptId}/revoke`, {
      method: "POST",
      body: JSON.stringify({ reason: reason.trim() }),
    })
    revalidatePath("/donations")
    return { success: true }
  } catch (error) {
    return toError(error)
  }
}
