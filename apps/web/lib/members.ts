import { apiCall, apiList } from "@/lib/api"
import type { ClubAccess, Member } from "@/lib/types/member"

/**
 * Server-side readers for the club's own data.
 *
 * Tenant scoping happens in the backend from the session — nothing here passes
 * a tenant id, so a caller cannot reach another club's members by construction.
 */

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ""
}

/**
 * The list sorts and filters on the client, so it asks for the whole set in
 * one response. The backend caps `per_page` at 100 — see the note in the
 * members page about what happens beyond that.
 */
export const MEMBER_PAGE_SIZE = 100

export async function listMembers(
  options: { page?: number; perPage?: number; search?: string } = {}
) {
  return apiList<Member>(
    `/api/v1/members${query({
      page: options.page,
      per_page: options.perPage,
      search: options.search,
    })}`
  )
}

export async function getMember(memberId: string) {
  return apiCall<Member>(`/api/v1/members/${memberId}`)
}

export async function getClubAccess() {
  return apiCall<ClubAccess>("/api/v1/club/access")
}
