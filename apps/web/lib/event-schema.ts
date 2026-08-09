import { z } from "zod"

import { EVENT_TYPE_KEYS } from "@/lib/types/event"

const optionalText = z
  .string()
  .optional()
  .transform((value) => {
    const trimmed = (value ?? "").trim()
    return trimmed === "" ? null : trimmed
  })

/** A `datetime-local` field the form leaves empty must not fail the parse. */
const optionalInstant = optionalText.refine(
  (value) => value === null || !Number.isNaN(new Date(value).getTime()),
  { message: "invalid datetime" }
)

const optionalCount = z
  .string()
  .optional()
  .transform((value) => {
    const trimmed = (value ?? "").trim()
    return trimmed === "" ? null : Number(trimmed)
  })
  .refine((value) => value === null || (Number.isInteger(value) && value >= 1), {
    message: "invalid participant limit",
  })

/** HTML checkboxes only reach FormData when checked. */
const checkbox = z
  .string()
  .optional()
  .transform((value) => value === "on" || value === "true")

const eventSchema = z
  .object({
    title: z.string().trim().min(1).max(255),
    description: optionalText,
    event_type: z.enum(EVENT_TYPE_KEYS).default("other"),
    location: optionalText,
    starts_at: z.string().refine((v) => !Number.isNaN(new Date(v).getTime()), {
      message: "invalid datetime",
    }),
    ends_at: optionalInstant,
    all_day: checkbox,
    registration_required: checkbox,
    registration_deadline: optionalInstant,
    max_participants: optionalCount,
  })
  .refine(
    (data) =>
      data.ends_at === null ||
      new Date(data.ends_at) >= new Date(data.starts_at),
    { message: "ends_at must not be before starts_at", path: ["ends_at"] }
  )
  .refine(
    (data) =>
      data.registration_deadline === null ||
      new Date(data.registration_deadline) <= new Date(data.starts_at),
    {
      message: "registration_deadline must not be after starts_at",
      path: ["registration_deadline"],
    }
  )

/**
 * Parses a submitted event form.
 *
 * Lives outside the Server Action file so it can be unit-tested: a `"use
 * server"` module may only export async functions. Same reason as
 * `parseMemberForm`.
 */
export function parseEventForm(formData: FormData) {
  return eventSchema.safeParse(Object.fromEntries(formData))
}
