export type DonationKind = "geldzuwendung" | "mitgliedsbeitrag"

/** A donation receipt as it was issued — every field frozen on the day. */
export type DonationReceipt = {
  id: string
  member_id: string | null
  donor_name: string
  donor_address: string | null
  amount: string
  received_on: string
  kind: DonationKind
  is_expense_waiver: boolean
  club_name: string
  exemption_kind: string
  exemption_date: string
  exemption_period: number | null
  tax_office: string
  tax_number: string
  purposes: string
  issued_at: string
  revoked_at: string | null
  revoke_reason: string | null
  verification_code: string
}

/**
 * Whether the club can issue receipts at all.
 *
 * Asked before the form is shown: telling somebody their tax number is
 * missing once they have typed a donor's address is a poor settings check.
 */
export type DonationReadiness = {
  ready: boolean
  missing: string[]
  membership_fees_deductible: boolean
}
