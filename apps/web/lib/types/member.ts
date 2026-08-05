/** A club member as returned by `/api/v1/members`. */
export type Member = {
  id: string
  member_number: string
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
  state: string | null
  country: string | null
  joined_at: string
  left_at: string | null
  status: string
  category: string | null
  notes: string | null
  iban: string | null
  bic: string | null
  account_holder: string | null
  sepa_mandate_reference: string | null
  sepa_mandate_date: string | null
  /** Set once the member has an account that can sign in. */
  user_id: string | null
  created_at: string
  updated_at: string
}

/** A member's membership in an external federation (DSB, BDS, …). */
export type MemberFederation = {
  id: string
  member_id: string
  federation: string
  federation_number: string | null
  joined_at: string | null
  left_at: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

/** An account that can sign in to the club. */
export type ClubAccessMember = {
  user_id: string
  name: string
  email: string
  image: string | null
  role: string
  is_active: boolean
  joined_at: string
}

/** An invitation that has neither been accepted nor withdrawn. */
export type ClubInvitation = {
  id: string
  email: string
  role: string
  expires_at: string
  created_at: string
  is_expired: boolean
  /** Set when the invitation was issued from a member record. */
  member_id: string | null
}

export type ClubAccess = {
  members: ClubAccessMember[]
  invitations: ClubInvitation[]
}
