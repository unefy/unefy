/** Mirrors `app/schemas/report.py`. Money arrives as a decimal string. */

export type CountByValue = {
  /** Null for records that carry no value — reported, not dropped. */
  value: string | null
  count: number
}

export type CountByBand = {
  band: "under_18" | "18_to_26" | "27_to_40" | "41_to_60" | "over_60"
  count: number
}

export type MembershipReport = {
  year: number
  /** Last year's closing, so `opening + joined - left === closing` holds. */
  opening: number
  joined: number
  left: number
  closing: number
  by_category: CountByValue[]
  by_gender: CountByValue[]
  by_age_band: CountByBand[]
  without_leaving_date: number
  without_birthday: number
}

export type DuesReportRow = {
  fee_name: string
  count: number
  charged: string
  paid: string
  open: string
  cancelled: string
  cancelled_count: number
}

export type DuesReport = {
  year: number
  by_fee: DuesReportRow[]
  totals: Omit<DuesReportRow, "fee_name">
}

export type ExpenseRow = {
  /** Null for invoices nobody has named yet. */
  supplier_name: string | null
  count: number
  total: string
  /** Of that, still unpaid. */
  open: string
}

export type ExpensesReport = {
  year: number
  by_supplier: ExpenseRow[]
  count: number
  total: string
  open: string
  /** Invoices the totals cannot see. Counted across all years — a row with
   *  no date belongs to none. */
  incomplete_count: number
}

export type AttendanceReport = {
  year: number
  sessions: number
  records: number
  members: number
  guests: number
  self_kept: number
  /** Null when the club held no sessions — not 0. */
  average_per_session: number | null
  by_month: { month: number; count: number }[]
}

export type AnnualReport = {
  year: number
  /** What the year picker may offer, newest first. */
  years: number[]
  membership: MembershipReport
  dues: DuesReport
  expenses: ExpensesReport
  attendance: AttendanceReport
}
