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
