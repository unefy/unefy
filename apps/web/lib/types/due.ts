/** The billing intervals the backend accepts — mirrors `INTERVAL_PATTERN`. */
export const FEE_INTERVAL_KEYS = [
  "yearly",
  "half_yearly",
  "quarterly",
  "monthly",
  "one_time",
] as const

export type FeeInterval = (typeof FEE_INTERVAL_KEYS)[number]

/** The states a due moves through. */
export const DUE_STATUS_KEYS = ["open", "paid", "cancelled"] as const

/** A fee type as returned by `/api/v1/dues/fee-types`. */
export type FeeType = {
  id: string
  name: string
  description: string | null
  amount: string
  interval: string
  is_active: boolean
}

/** A member↔fee assignment as returned by `/api/v1/dues/assignments`. */
export type MemberFeeAssignment = {
  id: string
  member_id: string
  fee_type_id: string
  valid_from: string
  valid_to: string | null
  note: string | null
}

/** Club totals as returned by `/api/v1/dues/summary`. Amounts are strings. */
export type DuesSummary = {
  open_count: number
  open_amount: string
  paid_count: number
  paid_amount: string
}

/**
 * A due as returned by `/api/v1/dues` and `/api/v1/dues/me`.
 *
 * Amounts are strings: the backend serialises Decimal in JSON mode, and money
 * must not pass through a float on the way to the screen.
 */
export type MyDue = {
  id: string
  member_id: string
  member_name: string | null
  fee_type_id: string
  fee_name: string
  amount: string
  period_start: string
  period_end: string
  due_date: string
  status: string
  paid_at: string | null
  payment_method: string | null
  note: string | null
}
