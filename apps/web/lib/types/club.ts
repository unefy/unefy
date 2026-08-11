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

  // SEPA creditor identity. Without the creditor id and IBAN the club cannot
  // produce a direct debit file at all — the backend refuses the export.
  sepa_creditor_id: string | null
  iban: string | null
  bic: string | null

  /** IANA name, e.g. "Europe/Berlin". The club's calendar day. */
  timezone: string

  /** Whether the club is organised in divisions (Sparten). Gates every
   * division picker in the UI. */
  has_divisions: boolean
  /** Whether the public join form accepts applications for this club. */
  applications_enabled: boolean

  /** What a donation receipt has to state about the club. */
  nonprofit_purposes: string | null
  tax_exemption_kind: string | null
  tax_exemption_date: string | null
  tax_exemption_period: number | null
  membership_fees_deductible: boolean

  /**
   * Modules activated by the club's sports (union over `sports.modules`),
   * e.g. `["shooting"]`. Gates module sections in nav and pages — the backend
   * enforces the same gate on every module endpoint.
   */
  modules: string[]

  /** The club's sports, primary first. */
  sports: ClubSport[]
}

export type ClubSport = {
  id: string
  key: string
  name: string
  icon: string | null
  is_primary: boolean
}
