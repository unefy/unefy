import { z } from "zod"

import { FEE_INTERVAL_KEYS } from "@/lib/types/due"

const optionalText = z
  .string()
  .optional()
  .transform((value) => {
    const trimmed = (value ?? "").trim()
    return trimmed === "" ? null : trimmed
  })

const optionalDate = optionalText.refine(
  (value) => value === null || /^\d{4}-\d{2}-\d{2}$/.test(value),
  { message: "invalid date" }
)

const requiredDate = z
  .string()
  .trim()
  .refine((value) => /^\d{4}-\d{2}-\d{2}$/.test(value), {
    message: "invalid date",
  })

/**
 * Money as typed by a treasurer.
 *
 * Accepts a comma as the decimal separator — a German keyboard produces
 * "12,50" — and hands on the dot form the API expects. Kept as a string all
 * the way: an amount that goes through a float comes back as 12.499999.
 */
const amount = z
  .string()
  .trim()
  .min(1)
  .transform((value) => value.replace(",", "."))
  .refine((value) => /^\d{1,8}(\.\d{1,2})?$/.test(value), {
    message: "invalid amount",
  })

const feeTypeSchema = z.object({
  name: z.string().trim().min(1).max(255),
  description: optionalText,
  amount,
  interval: z.enum(FEE_INTERVAL_KEYS).default("yearly"),
})

const assignmentSchema = z
  .object({
    member_id: z.string().uuid(),
    fee_type_id: z.string().uuid(),
    valid_from: requiredDate,
    valid_to: optionalDate,
    note: optionalText,
  })
  .refine(
    (data) => data.valid_to === null || data.valid_to >= data.valid_from,
    { message: "valid_to must not be before valid_from", path: ["valid_to"] }
  )

const paymentSchema = z.object({
  paid_at: optionalDate,
  payment_method: optionalText,
  note: optionalText,
})

/**
 * Parsers for the dues forms.
 *
 * They live outside the Server Action file so they can be unit-tested: a
 * `"use server"` module may only export async functions. Same reason as
 * `parseMemberForm`.
 */
export function parseFeeTypeForm(formData: FormData) {
  return feeTypeSchema.safeParse(Object.fromEntries(formData))
}

export function parseAssignmentForm(formData: FormData) {
  return assignmentSchema.safeParse(Object.fromEntries(formData))
}

export function parsePaymentForm(formData: FormData) {
  return paymentSchema.safeParse(Object.fromEntries(formData))
}

/**
 * Query of the SEPA export proxy route.
 *
 * Validated here rather than passed through, so a hand-edited URL cannot reach
 * the backend with nonsense. The collection date is optional — the backend
 * picks the earliest legal date when it is absent.
 */
export const sepaExportQuerySchema = z.object({
  year: z
    .string()
    .trim()
    .refine((value) => /^\d{4}$/.test(value), { message: "invalid year" })
    .transform(Number)
    .refine((value) => value >= 2000 && value <= 2100, {
      message: "year out of range",
    }),
  collection_date: optionalDate,
})
