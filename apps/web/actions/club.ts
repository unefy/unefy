"use server"

import { revalidatePath } from "next/cache"
import { z } from "zod"

import { apiCall, ApiError } from "@/lib/api"
import type { Club } from "@/lib/types/club"

export type ActionResult<T = unknown> =
  { success: true; data?: T } | { success: false; error: string }

function toError<T>(error: unknown): ActionResult<T> {
  if (error instanceof ApiError) {
    if (error.status === 403) return { success: false, error: "forbidden" }
    if (error.status === 404) return { success: false, error: "notFound" }
    if (error.status === 422) return { success: false, error: "validation" }
    return { success: false, error: "unknown" }
  }
  return { success: false, error: "unreachable" }
}

/** Empty form fields mean "not set", not an empty string. */
const optionalText = z
  .string()
  .trim()
  .transform((value) => (value === "" ? null : value))
  .nullable()

const optionalDate = optionalText.refine(
  (value) => value === null || /^\d{4}-\d{2}-\d{2}$/.test(value),
  { message: "invalid date" }
)

const clubSchema = z.object({
  name: z.string().trim().min(2).max(255),
  short_name: optionalText,

  // Contact
  email: optionalText.refine(
    (value) => value === null || z.string().email().safeParse(value).success,
    { message: "invalid email" }
  ),
  phone: optionalText,
  website: optionalText,

  // Address
  street: optionalText,
  zip_code: optionalText,
  city: optionalText,
  state: optionalText,
  country: optionalText,

  // Club details
  founded_at: optionalDate,
  registration_number: optionalText,
  registration_court: optionalText,
  tax_number: optionalText,
  tax_office: optionalText,
  // Optional because the field is only rendered while the non-profit switch is
  // on — an absent key must mean "no date", not "invalid form". Requiring it
  // locked every non-charitable club out of saving this page at all.
  nonprofit_since: optionalDate.optional(),

  // SEPA creditor identity — the club's side of a direct debit.
  sepa_creditor_id: optionalText,
  iban: optionalText,
  bic: optionalText,

  // The zone the club's calendar day is resolved against. Validated properly
  // in the backend against the actual zone database — a typo here would shift
  // every attendance date by a day.
  timezone: z.string().trim().min(1).max(64),
})

export async function updateClubAction(
  _prev: ActionResult | undefined,
  formData: FormData
): Promise<ActionResult<Club>> {
  const raw = Object.fromEntries(formData)
  const parsed = clubSchema.safeParse(raw)
  if (!parsed.success) return { success: false, error: "validation" }

  // An unchecked checkbox is absent from FormData rather than "false".
  const isNonprofit = formData.get("is_nonprofit") === "on"
  const applicationsEnabled = formData.get("applications_enabled") === "on"

  try {
    const club = await apiCall<Club>("/api/v1/club", {
      method: "PATCH",
      body: JSON.stringify({
        ...parsed.data,
        is_nonprofit: isNonprofit,
        applications_enabled: applicationsEnabled,
        // Meaningless without the flag, and leaving it behind would suggest a
        // status the club no longer claims.
        nonprofit_since: isNonprofit
          ? (parsed.data.nonprofit_since ?? null)
          : null,
      }),
    })
    revalidatePath("/settings")
    // Times across the app are rendered in the club's zone, so a change here
    // invalidates more than this page.
    revalidatePath("/attendance", "layout")
    return { success: true, data: club }
  } catch (error) {
    return toError(error)
  }
}

export async function setClubSportsAction(
  sportIds: string[],
  primarySportId: string
): Promise<ActionResult> {
  const parsed = z
    .object({
      sport_ids: z.array(z.string().uuid()).min(1),
      primary_sport_id: z.string().uuid(),
    })
    .refine((value) => value.sport_ids.includes(value.primary_sport_id))
    .safeParse({ sport_ids: sportIds, primary_sport_id: primarySportId })
  if (!parsed.success) return { success: false, error: "validation" }

  try {
    await apiCall("/api/v1/club/sports", {
      method: "PUT",
      body: JSON.stringify(parsed.data),
    })
  } catch (error) {
    return toError(error)
  }

  // Sports gate module nav and pages, so everything may look different now.
  revalidatePath("/", "layout")
  return { success: true }
}
