import { apiCall, apiList } from "@/lib/api"
import type { FeeType, MemberFeeAssignment, MyDue } from "@/lib/types/due"

/** The caller's own dues — member resolution happens in the backend. */
export async function listMyDues() {
  return (await apiList<MyDue>("/api/v1/dues/me?per_page=100")).data
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

export async function listFeeTypes() {
  return apiCall<FeeType[]>("/api/v1/dues/fee-types")
}
