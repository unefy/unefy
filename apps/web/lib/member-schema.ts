import { z } from "zod"

import { GENDER_KEYS, MEMBER_STATUS_KEYS } from "@/lib/labels"

/**
 * An optional form field.
 *
 * `.optional()` matters as much as the empty-string handling: a field that is
 * not rendered at all (`left_at` when creating) never reaches FormData, so a
 * plain string schema would reject the whole form.
 */
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

const memberSchema = z.object({
  first_name: z.string().trim().min(1).max(255),
  last_name: z.string().trim().min(1).max(255),
  email: optionalText.refine(
    (value) => value === null || z.string().email().safeParse(value).success,
    { message: "invalid email" }
  ),
  phone: optionalText,
  mobile: optionalText,
  birthday: optionalDate,
  gender: optionalText.refine(
    (value) => value === null || (GENDER_KEYS as readonly string[]).includes(value),
    { message: "invalid gender" }
  ),
  street: optionalText,
  zip_code: optionalText,
  city: optionalText,
  country: optionalText,
  joined_at: optionalDate,
  left_at: optionalDate,
  status: z.enum(MEMBER_STATUS_KEYS).default("active"),
  category: optionalText,
  notes: optionalText,
  iban: optionalText,
  bic: optionalText,
  account_holder: optionalText,
  // The signed mandate behind the bank details. The SEPA export skips a member
  // who has an IBAN but no mandate — collecting without one is not allowed.
  sepa_mandate_reference: optionalText,
  sepa_mandate_date: optionalDate,
})

/**
 * Parses a submitted member form.
 *
 * Lives outside the Server Action file so it can be unit-tested: a `"use
 * server"` module may only export async functions.
 */
export function parseMemberForm(formData: FormData) {
  return memberSchema.safeParse(Object.fromEntries(formData))
}
