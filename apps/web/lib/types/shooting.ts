/** Types for the shooting module (`/api/v1/modules/shooting/*`). */

export type ShootingRule = {
  id: string
  rule_key: string
  label: string
  window_months: number
  min_total_days: number | null
  min_distinct_months: number | null
  created_at: string
  updated_at: string
}

export type ProofEvaluation = {
  member_id: string
  rule_key: string
  period_start: string
  period_end: string
  session_count: number
  months_covered: number
  passed: boolean
  /**
   * Of the counted days, those resting on nothing but the member's own word —
   * and of those, the ones on which they checked other people in. The board
   * needs to see this before signing anything: a supervisor has no other way to
   * record their own attendance, so the number is expected to be non-zero and
   * only becomes a question when nothing corroborates it.
   */
  self_certified_days: number
  corroborated_self_days: number
}

export type ShootingCertificate = {
  id: string
  member_id: string
  member_name: string | null
  rule_key: string
  period_start: string
  period_end: string
  session_count: number
  months_covered: number
  self_certified_days: number
  corroborated_self_days: number
  result: "passed" | "failed"
  issued_at: string
  issued_by_user_id: string
  revoked_at: string | null
  revoke_reason: string | null
  content_hash: string
  verification_code: string
}

/** `GET /api/v1/attendance/proof-chain/status` — core, not module. */
export type ProofChainStatus = {
  length: number
  valid: boolean
  broken_at_seq: number | null
  head_hash: string | null
  anchored_to_seq: number | null
  anchored_at: string | null
}
