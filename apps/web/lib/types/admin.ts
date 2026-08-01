/** Types for the platform admin area (`/admin`). Mirrors `app/schemas/admin.py`. */

export type PaginationMeta = {
  total: number
  page: number
  per_page: number
  total_pages: number
}

export type AdminTenant = {
  id: string
  name: string
  short_name: string | null
  slug: string
  city: string | null
  is_active: boolean
  created_at: string
  member_count: number
  user_count: number
}

/** A single club, with the contact fields the list does not carry. */
export type AdminTenantDetail = AdminTenant & {
  zip_code: string | null
  street: string | null
  country: string | null
  email: string | null
  phone: string | null
  website: string | null
  founded_at: string | null
}

/** A login account attached to a club. */
export type AdminTenantUser = {
  user_id: string
  name: string
  email: string
  role: string
  is_active: boolean
}

/**
 * A club member as the platform admin sees them. Deliberately narrow — the
 * backend withholds banking details, address, birthday and notes.
 */
export type AdminTenantMember = {
  id: string
  member_number: string
  first_name: string
  last_name: string
  status: string
  category: string | null
  joined_at: string
  left_at: string | null
  has_account: boolean
}

export type AdminUser = {
  id: string
  email: string
  name: string
  image: string | null
  email_verified: boolean
  locale: string | null
  is_superuser: boolean
  created_at: string
}

export type AdminMembership = {
  tenant_id: string
  tenant_name: string
  role: string
  is_active: boolean
}

export type AuditLogEntry = {
  id: string
  actor_user_id: string
  actor_email: string | null
  impersonator_id: string | null
  impersonator_email: string | null
  action: string
  target_type: string | null
  target_id: string | null
  tenant_id: string | null
  payload: Record<string, unknown> | null
  ip_address: string | null
  created_at: string
}

export type Sport = {
  id: string
  key: string
  name: string
  description: string | null
  icon: string | null
  sort_order: number
  is_active: boolean
  modules: string[]
  unit_count: number
  discipline_count: number
}

export type SportModule = {
  key: string
  label: string
}

export type CatalogUnit = {
  id: string
  sport_id: string
  name: string
  symbol: string | null
  sort_order: number
  is_active: boolean
}

export type CatalogDiscipline = {
  id: string
  sport_id: string | null
  slug: string
  name: string
  short_name: string | null
  description: string | null
  federation: string
  federation_id: string | null
  category: string
  distance: string | null
  caliber: string | null
  target_type: string | null
  scoring_unit: string
  scoring_mode: string
  shot_count: number | null
  is_official: boolean
  is_active: boolean
}
