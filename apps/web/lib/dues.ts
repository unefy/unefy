import { apiCall, apiList } from "@/lib/api"
import type {
  DuesSummary,
  FeeType,
  MemberFeeAssignment,
  MyDue,
} from "@/lib/types/due"

/**
 * Server-side readers for dues.
 *
 * Tenant scoping happens in the backend from the session — nothing here passes
 * a tenant id, so a caller cannot reach another club's books by construction.
 */

/** The list sorts and filters on the client, so it asks for one full page. */
export const DUES_PAGE_SIZE = 100

/** The caller's own dues — member resolution happens in the backend. */
export async function listMyDues() {
  return (await apiList<MyDue>("/api/v1/dues/me?per_page=100")).data
}

/** All dues, board view. */
export async function listDues(
  options: { page?: number; perPage?: number; status?: string; year?: number } = {}
) {
  const params = new URLSearchParams({
    page: String(options.page ?? 1),
    per_page: String(options.perPage ?? DUES_PAGE_SIZE),
  })
  if (options.status) params.set("status", options.status)
  if (options.year) params.set("year", String(options.year))
  return apiList<MyDue>(`/api/v1/dues?${params}`)
}

/** One member's dues, board view. */
export async function listMemberDues(memberId: string) {
  return (await apiList<MyDue>(`/api/v1/dues?member_id=${memberId}&per_page=100`))
    .data
}

/** One member's fee assignments. */
export async function listMemberFeeAssignments(memberId: string) {
  return (
    await apiList<MemberFeeAssignment>(
      `/api/v1/dues/assignments?member_id=${memberId}`
    )
  ).data
}

export async function listFeeTypes(includeInactive = false) {
  return apiCall<FeeType[]>(
    `/api/v1/dues/fee-types${includeInactive ? "?include_inactive=true" : ""}`
  )
}

/**
 * Open/paid totals for the whole club, board view.
 *
 * Amounts arrive as strings — the backend serialises Decimal in JSON mode, and
 * money must not pass through a float on the way to the screen.
 */
export async function getDuesSummary(year?: number) {
  return apiCall<DuesSummary>(
    `/api/v1/dues/summary${year ? `?year=${year}` : ""}`
  )
}
