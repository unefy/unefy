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
