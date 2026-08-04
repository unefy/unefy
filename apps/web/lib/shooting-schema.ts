import { z } from "zod"

/**
 * Validation for the shooting module's forms.
 *
 * Extracted from the actions so it can be unit-tested — the actions themselves
 * touch network and cookies (see `__tests__/lib/shooting-schema.test.ts`).
 * Mirrors the backend's schemas; the backend remains the boundary.
 */

const optionalCount = z
  .string()
  .trim()
  .transform((value) => (value === "" ? null : Number(value)))
  .nullable()
  .refine(
    (value) => value === null || (Number.isInteger(value) && value >= 1),
    { message: "must be a positive integer" }
  )

export const ruleSchema = z
  .object({
    rule_key: z
      .string()
      .trim()
      .min(1)
      .max(50)
      .regex(/^[a-z0-9_-]+$/),
    label: z.string().trim().min(1).max(255),
    window_months: z.coerce.number().int().min(1).max(60),
    min_total_days: optionalCount,
    min_distinct_months: optionalCount,
  })
  .refine(
    (data) => data.min_total_days !== null || data.min_distinct_months !== null,
    { message: "at least one criterion" }
  )

export function parseRuleForm(formData: FormData) {
  return ruleSchema.safeParse(Object.fromEntries(formData))
}

/** Mirrors the backend: a revocation without a reason is not a revocation. */
export const revokeReasonSchema = z.string().trim().min(3).max(1000)

/** ISO calendar dates, as `<input type="date">` submits them. */
export const isoDateSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}$/)

export const rangeBookQuerySchema = z
  .object({ from: isoDateSchema, to: isoDateSchema })
  .refine((data) => data.from <= data.to, { message: "from after to" })
