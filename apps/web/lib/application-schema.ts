import { z } from "zod"

import { GENDER_KEYS } from "@/lib/labels"

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

const optionalId = optionalText.refine(
  (value) => value === null || z.string().uuid().safeParse(value).success,
  { message: "invalid id" }
)

/** A checkbox: present in FormData only when ticked. */
const checkbox = z
  .string()
  .optional()
  .transform((value) => value === "on" || value === "true")

const applicationSchema = z
  .object({
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
      (value) =>
        value === null || (GENDER_KEYS as readonly string[]).includes(value),
      { message: "invalid gender" }
    ),
    street: optionalText,
    zip_code: optionalText,
    city: optionalText,
    country: optionalText,
    message: optionalText,
    fee_type_id: optionalId,
    division_id: optionalId,
    iban: optionalText,
    bic: optionalText,
    account_holder: optionalText,
    grant_sepa_mandate: checkbox,
    privacy_accepted: checkbox,
    consent_photos: checkbox,
    consent_newsletter: checkbox,
    consent_directory: checkbox,
  })
  // Checked here as well as in the backend so the applicant is told which box
  // is missing instead of being handed a generic 422 after a full round trip.
  .refine((data) => data.privacy_accepted, { path: ["privacy_accepted"] })
  .refine((data) => !data.grant_sepa_mandate || data.iban !== null, {
    path: ["iban"],
  })

export type ApplicationInput = z.infer<typeof applicationSchema>

/** Parses the public join form. Outside the action file so it is testable. */
export function parseApplicationForm(formData: FormData) {
  return applicationSchema.safeParse(Object.fromEntries(formData.entries()))
}
