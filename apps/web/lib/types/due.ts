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

/** A due as returned by `/api/v1/dues/me`. */
export type MyDue = {
  id: string
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
