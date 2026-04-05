// Status is now configurable per tenant — no hardcoded union type

export interface Member {
  id: string
  member_number: string
  first_name: string
  last_name: string
  email: string | null
  phone: string | null
  mobile: string | null
  birthday: string | null
  street: string | null
  zip_code: string | null
  city: string | null
  state: string | null
  country: string | null
  joined_at: string
  left_at: string | null
  status: string
  category: string | null
  notes: string | null
  user_id: string | null
  created_at: string
  updated_at: string
}

export interface MemberCreate {
  first_name: string
  last_name: string
  email?: string | null
  phone?: string | null
  mobile?: string | null
  birthday?: string | null
  street?: string | null
  zip_code?: string | null
  city?: string | null
  state?: string | null
  country?: string | null
  joined_at?: string | null
  status?: string
  category?: string | null
  notes?: string | null
}

export interface MemberUpdate extends Partial<MemberCreate> {
  left_at?: string | null
}

export interface MemberListResponse {
  data: Member[]
  meta: {
    total: number
    page: number
    per_page: number
    total_pages: number
    status_counts: Record<string, number>
  }
}
