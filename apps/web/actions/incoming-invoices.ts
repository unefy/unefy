"use server"

import { revalidatePath } from "next/cache"
import { z } from "zod"

import { apiCall, ApiError } from "@/lib/api"
import type { IncomingInvoice } from "@/lib/types/incoming-invoices"

/**
 * Everything about an invoice that fits in a JSON body.
 *
 * The upload is deliberately not here — a server action's body is capped at
 * 1 MB and a scan is not. It goes through
 * `app/api/incoming-invoices/upload/route.ts`, which streams.
 */

export type ActionResult<T = unknown> =
  { success: true; data?: T } | { success: false; error: string }

function toError<T>(error: unknown): ActionResult<T> {
  if (error instanceof ApiError) {
    if (error.status === 403) return { success: false, error: "forbidden" }
    if (error.status === 404) return { success: false, error: "notFound" }
    // The one worth naming: this supplier's invoice number is already filed.
    if (error.status === 409) return { success: false, error: "duplicate" }
    if (error.status === 422) return { success: false, error: "validation" }
    return { success: false, error: "unknown" }
  }
  return { success: false, error: "unreachable" }
}

const INVOICES_PATH = "/incoming-invoices"

/** Empty strings from a form mean "cleared", not "unchanged". */
const optionalText = z
  .string()
  .trim()
  .max(255)
  .transform((value) => (value === "" ? null : value))

const optionalAmount = z
  .string()
  .trim()
  .transform((value) => (value === "" ? null : value))
  .refine((value) => value === null || /^\d+([.,]\d{1,2})?$/.test(value), {
    message: "amount",
  })
  // A German keyboard types a decimal comma. Refusing it would be pedantry
  // aimed at the one person who has the invoice in their hand.
  .transform((value) => (value === null ? null : value.replace(",", ".")))

const optionalDate = z
  .string()
  .trim()
  .transform((value) => (value === "" ? null : value))
  .refine((value) => value === null || /^\d{4}-\d{2}-\d{2}$/.test(value), {
    message: "date",
  })

const updateSchema = z.object({
  supplier_name: optionalText,
  supplier_vat_id: optionalText.pipe(z.string().max(30).nullable()),
  invoice_number: optionalText.pipe(z.string().max(100).nullable()),
  invoice_date: optionalDate,
  due_date: optionalDate,
  gross_amount: optionalAmount,
  net_amount: optionalAmount,
  tax_amount: optionalAmount,
  note: z
    .string()
    .trim()
    .max(2000)
    .transform((value) => (value === "" ? null : value)),
})

export async function updateInvoiceAction(
  id: string,
  input: Record<string, string>
): Promise<ActionResult<IncomingInvoice>> {
  const parsed = updateSchema.safeParse(input)
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    const data = await apiCall<IncomingInvoice>(
      `/api/v1/incoming-invoices/${id}`,
      { method: "PATCH", body: JSON.stringify(parsed.data) }
    )
    revalidatePath(INVOICES_PATH)
    revalidatePath(`${INVOICES_PATH}/${id}`)
    return { success: true, data }
  } catch (error) {
    return toError(error)
  }
}

export async function markInvoicePaidAction(
  id: string,
  paidOn: string | null
): Promise<ActionResult<IncomingInvoice>> {
  if (paidOn !== null && !/^\d{4}-\d{2}-\d{2}$/.test(paidOn)) {
    return { success: false, error: "validation" }
  }
  return call(id, "pay", { paid_on: paidOn })
}

export async function reopenInvoiceAction(
  id: string
): Promise<ActionResult<IncomingInvoice>> {
  return call(id, "reopen")
}

export async function cancelInvoiceAction(
  id: string
): Promise<ActionResult<IncomingInvoice>> {
  return call(id, "cancel")
}

export async function deleteInvoiceAction(id: string): Promise<ActionResult> {
  try {
    await apiCall(`/api/v1/incoming-invoices/${id}`, { method: "DELETE" })
    revalidatePath(INVOICES_PATH)
    return { success: true }
  } catch (error) {
    return toError(error)
  }
}

async function call(
  id: string,
  action: string,
  body?: unknown
): Promise<ActionResult<IncomingInvoice>> {
  try {
    const data = await apiCall<IncomingInvoice>(
      `/api/v1/incoming-invoices/${id}/${action}`,
      { method: "POST", body: JSON.stringify(body ?? {}) }
    )
    revalidatePath(INVOICES_PATH)
    revalidatePath(`${INVOICES_PATH}/${id}`)
    return { success: true, data }
  } catch (error) {
    return toError(error)
  }
}
