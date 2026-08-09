import { z } from "zod"

import {
  COMPETITION_TYPE_KEYS,
  SCORING_MODE_KEYS,
} from "@/lib/types/competition"

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

const competitionSchema = z
  .object({
    name: z.string().trim().min(1).max(255),
    description: optionalText,
    competition_type: z.enum(COMPETITION_TYPE_KEYS).default("competition"),
    start_date: requiredDate,
    end_date: optionalDate,
    scoring_mode: z.enum(SCORING_MODE_KEYS).default("highest_wins"),
    // Free text on purpose: Punkte, Ringe, Sekunden, Meter — the club knows
    // what it measures, and hard-coding a list would exclude a sport.
    scoring_unit: z.string().trim().min(1).max(50),
    // Comma-separated in the form, a list in the API.
    disciplines: z
      .string()
      .optional()
      .transform((value) => {
        const parts = (value ?? "")
          .split(",")
          .map((part) => part.trim())
          .filter(Boolean)
        return parts.length > 0 ? parts : null
      }),
  })
  .refine(
    (data) => data.end_date === null || data.end_date >= data.start_date,
    { message: "end_date must not be before start_date", path: ["end_date"] }
  )

const sessionSchema = z.object({
  name: optionalText,
  date: requiredDate,
  location: optionalText,
  discipline: optionalText,
})

/**
 * A result as typed by whoever keeps the score.
 *
 * Accepts a comma as the decimal separator, like the dues amounts — and stays
 * a string until the API, because a time of 12.345 s must not be rounded on
 * the way there.
 */
const scoreValue = z
  .string()
  .trim()
  .min(1)
  .transform((value) => value.replace(",", "."))
  .refine((value) => /^\d{1,8}(\.\d{1,3})?$/.test(value), {
    message: "invalid score",
  })

const entrySchema = z.object({
  member_id: z.string().uuid(),
  score_value: scoreValue,
  discipline: optionalText,
  notes: optionalText,
})

/**
 * Parsers for the competition forms.
 *
 * They live outside the Server Action file so they can be unit-tested: a
 * `"use server"` module may only export async functions.
 */
export function parseCompetitionForm(formData: FormData) {
  return competitionSchema.safeParse(Object.fromEntries(formData))
}

export function parseSessionForm(formData: FormData) {
  return sessionSchema.safeParse(Object.fromEntries(formData))
}

export function parseEntryForm(formData: FormData) {
  return entrySchema.safeParse(Object.fromEntries(formData))
}
