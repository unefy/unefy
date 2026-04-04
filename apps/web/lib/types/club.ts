export interface Club {
  id: string
  name: string
  short_name: string | null
  slug: string
  email: string | null
  phone: string | null
  website: string | null
  street: string | null
  zip_code: string | null
  city: string | null
  state: string | null
  country: string | null
  description: string | null
  logo_url: string | null
  founded_at: string | null
  registration_number: string | null
  registration_court: string | null
  tax_number: string | null
  tax_office: string | null
  is_nonprofit: boolean
  nonprofit_since: string | null
  member_number_format: string
  member_number_prefix: string | null
  member_number_next: number
}
