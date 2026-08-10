import { API_BASE, apiCall } from "@/lib/api"
import type {
  JoinForm,
  MembershipApplication,
  MembershipApplicationDetail,
} from "@/lib/types/application"

/** Applications for the board, newest first. Bank details are not in here. */
export async function listApplications(status?: string) {
  const query = status ? `?status=${encodeURIComponent(status)}` : ""
  return apiCall<MembershipApplication[]>(`/api/v1/applications${query}`)
}

/** One application, with the bank details — the page a decision is made on. */
export async function getApplication(id: string) {
  return apiCall<MembershipApplicationDetail>(`/api/v1/applications/${id}`)
}

/**
 * The public join form's data, fetched without a session.
 *
 * Deliberately not `apiCall`: that one forwards the visitor's session cookie,
 * and this page has no visitor with a session. Returns null for a club that
 * has not opened its form — the page renders the same "not found" either way.
 */
export async function getJoinForm(slug: string): Promise<JoinForm | null> {
  try {
    const response = await fetch(
      `${API_BASE}/join/${encodeURIComponent(slug)}`,
      { cache: "no-store" }
    )
    if (!response.ok) return null
    const body = (await response.json()) as { data?: JoinForm }
    return body.data ?? null
  } catch {
    return null
  }
}
