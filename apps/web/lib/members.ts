import { cache } from "react"

import { apiCall, apiList, collectPages, type PaginationMeta } from "@/lib/api"
import type { ClubAccess, Member, MemberFederation } from "@/lib/types/member"

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

/**
 * Every member, across as many pages as the API caps at 100.
 *
 * The list sorts and filters in the table, so it has to hold the whole club:
 * a table that sorts the first hundred rows looks sorted and is not.
 */
export async function listAllMembers(search?: string) {
  return collectPages<Member>((page) =>
    apiList<Member>(
      `/api/v1/members${query({ page, per_page: MEMBER_PAGE_SIZE, search })}`
    )
  )
}

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

/**
 * Club-wide tallies per member status, for the dashboard.
 *
 * Asks for a single row: the counts sit in `meta` and are computed over the
 * whole club, not over the page — fetching 100 members to count them would be
 * both slower and wrong beyond the page cap.
 */
export async function getMemberStatusCounts() {
  const { meta } = await apiList<Member>("/api/v1/members?per_page=1")
  const withCounts = meta as PaginationMeta & {
    status_counts?: Record<string, number>
  }
  return { total: withCounts.total, counts: withCounts.status_counts ?? {} }
}

/**
 * `cache()` dedupes within one request: the member-detail layout fetches the
 * record for its header and the overview tab fetches it again — one HTTP call.
 */
export const getMember = cache(async (memberId: string) => {
  return apiCall<Member>(`/api/v1/members/${memberId}`)
})

/**
 * The caller's own member record — self-service, any role. 404s when the
 * account is not linked to a member; callers show an explanation, not an
 * error, because unlinked accounts (treasurer, external trainer) are a
 * normal state.
 */
export async function getMyMember() {
  return apiCall<Member>("/api/v1/members/me")
}

export async function listMemberFederations(memberId: string) {
  const result = await apiList<MemberFederation>(
    `/api/v1/members/${memberId}/federations`
  )
  return result.data
}

export async function getClubAccess() {
  return apiCall<ClubAccess>("/api/v1/club/access")
}
