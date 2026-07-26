export type FeeInterval =
  | "yearly"
  | "half_yearly"
  | "quarterly"
  | "monthly"
  | "one_time"

export type DueStatus = "open" | "paid" | "cancelled"

export interface FeeType {
  id: string
  name: string
  description: string | null
  amount: string
  interval: FeeInterval
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface FeeTypeCreate {
  name: string
  description?: string | null
  amount: string
  interval: FeeInterval
  is_active?: boolean
}

export type FeeTypeUpdate = Partial<FeeTypeCreate>

export interface MemberFee {
  id: string
  member_id: string
  fee_type_id: string
  valid_from: string
  valid_to: string | null
  note: string | null
  created_at: string
  updated_at: string
}

export interface MemberFeeCreate {
  member_id: string
  fee_type_id: string
  valid_from: string
  valid_to?: string | null
  note?: string | null
}

export interface Due {
  id: string
  member_id: string
  member_name: string | null
  fee_type_id: string
  fee_name: string
  amount: string
  period_start: string
  period_end: string
  due_date: string
  status: DueStatus
  paid_at: string | null
  payment_method: string | null
  note: string | null
  created_at: string
  updated_at: string
}

export interface DueListResponse {
  data: Due[]
  meta: {
    total: number
    page: number
    per_page: number
    total_pages: number
  }
}

export interface DueSummary {
  open_count: number
  open_amount: string
  paid_count: number
  paid_amount: string
}
