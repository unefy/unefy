/** What the public join form needs to render. */
export type JoinForm = {
  club_name: string
  fee_types: { id: string; name: string; amount: string; interval: string }[]
  divisions: { id: string; name: string }[]
  has_divisions: boolean
}

/** An application as the board's list shows it — no bank details. */
export type MembershipApplication = {
  id: string
  status: "pending" | "accepted" | "rejected"
  first_name: string
  last_name: string
  email: string | null
  phone: string | null
  mobile: string | null
  birthday: string | null
  gender: string | null
  street: string | null
  zip_code: string | null
  city: string | null
  country: string | null
  message: string | null
  fee_type_id: string | null
  division_id: string | null
  has_sepa_mandate: boolean
  privacy_accepted_at: string
  consent_photos: boolean
  consent_newsletter: boolean
  consent_directory: boolean
  decided_at: string | null
  decision_note: string | null
  member_id: string | null
  created_at: string
}

/** The single application, where deciding happens — bank details included. */
export type MembershipApplicationDetail = MembershipApplication & {
  iban: string | null
  bic: string | null
  account_holder: string | null
}
