/** The club record as returned by `/api/v1/club`. */
export type Club = {
  id: string
  name: string
  short_name: string | null
  /** Assigned at creation and not editable here — it addresses the club. */
  slug: string

  // Contact
  email: string | null
  phone: string | null
  website: string | null

  // Address
  street: string | null
  zip_code: string | null
  city: string | null
  state: string | null
  country: string | null

  // Club details
  description: string | null
  founded_at: string | null
  registration_number: string | null
  registration_court: string | null
  tax_number: string | null
  tax_office: string | null
  is_nonprofit: boolean
  nonprofit_since: string | null

  /** IANA name, e.g. "Europe/Berlin". The club's calendar day. */
  timezone: string
}
