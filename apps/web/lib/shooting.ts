import { apiCall, apiList } from "@/lib/api"
import type {
  ProofChainStatus,
  ShootingCertificate,
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

export async function getProofChainStatus() {
  return apiCall<ProofChainStatus>("/api/v1/attendance/proof-chain/status")
}
