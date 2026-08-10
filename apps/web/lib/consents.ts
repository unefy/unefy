import { apiCall } from "@/lib/api"
import type { ConsentOverview } from "@/lib/types/consent"

/** One member's consents, current state and the trail behind it. */
export async function getMemberConsents(memberId: string) {
  return apiCall<ConsentOverview>(`/api/v1/members/${memberId}/consents`)
}

/** The caller's own consents. */
export async function getOwnConsents() {
  return apiCall<ConsentOverview>("/api/v1/members/me/consents")
}
