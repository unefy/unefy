import { apiCall } from "@/lib/api"
import type { DonationReadiness, DonationReceipt } from "@/lib/types/donation"

/** Issued receipts, newest donation first. */
export async function listReceipts(
  options: { memberId?: string; year?: number } = {}
) {
  const params = new URLSearchParams()
  if (options.memberId) params.set("member_id", options.memberId)
  if (options.year) params.set("year", String(options.year))
  const query = params.toString()
  return apiCall<DonationReceipt[]>(
    `/api/v1/donations${query ? `?${query}` : ""}`
  )
}

/** Whether the club's tax data is complete enough to issue. */
export async function getDonationReadiness() {
  return apiCall<DonationReadiness>("/api/v1/donations/readiness")
}
