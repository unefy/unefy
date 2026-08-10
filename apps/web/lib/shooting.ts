import { apiCall, apiList } from "@/lib/api"
import type {
  ProofChainStatus,
  ProofEvaluation,
  ShootingCertificate,
  ShootingRecordDetail,
  ShootingRule,
} from "@/lib/types/shooting"

/**
 * Server-side readers for the shooting module.
 *
 * Everything under `/modules/shooting` is gated by the backend: a club whose
 * sports carry no shooting module gets a 403, which pages translate to
 * `notFound()` — the section simply does not exist for them.
 */

export async function listShootingRules() {
  return apiCall<ShootingRule[]>("/api/v1/modules/shooting/rules")
}

export async function listShootingCertificates(
  options: { page?: number; perPage?: number } = {}
) {
  const perPage = options.perPage ?? 100
  return apiList<ShootingCertificate>(
    `/api/v1/modules/shooting/certificates?page=${options.page ?? 1}&per_page=${perPage}`
  )
}

/** The live proof numbers for one member against one rule. */
export async function evaluateProof(memberId: string, ruleKey: string) {
  return apiCall<ProofEvaluation>(
    `/api/v1/modules/shooting/proof/${memberId}?rule_key=${encodeURIComponent(ruleKey)}`
  )
}

export async function getProofChainStatus() {
  return apiCall<ProofChainStatus>("/api/v1/attendance/proof-chain/status")
}

/**
 * What was shot at one evening, keyed by attendance record.
 *
 * One request for the whole list rather than one per row. Read from the module
 * rather than folded into the attendance response: `AttendanceRecord` belongs to
 * the core that every club has, a discipline to a module most clubs do not.
 */
/** The caller's own shooting details, keyed by attendance record. */
export async function listOwnShootingDetails() {
  return apiCall<ShootingRecordDetail[]>(
    "/api/v1/modules/shooting/me/records"
  )
}

export async function listSessionShootingDetails(sessionId: string) {
  return apiCall<ShootingRecordDetail[]>(
    `/api/v1/modules/shooting/records?session_id=${sessionId}`
  )
}

/** The disciplines the club offers, for the entry form's select. */
