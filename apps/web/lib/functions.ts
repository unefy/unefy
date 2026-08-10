import { apiCall } from "@/lib/api"
import type {
  ClubDivision,
  ClubFunction,
  FunctionHolder,
  MemberFunction,
} from "@/lib/types/functions"

/** The club's list of offices, inactive ones included (the settings page
 * shows them greyed out rather than hiding them). */
export async function listFunctions() {
  return apiCall<ClubFunction[]>("/api/v1/functions?include_inactive=true")
}

/** Only offices that can currently be assigned. */
export async function listActiveFunctions() {
  return apiCall<ClubFunction[]>("/api/v1/functions")
}

/** A member's terms of office, newest first, history included. */
export async function listMemberFunctions(memberId: string) {
  return apiCall<MemberFunction[]>(`/api/v1/members/${memberId}/functions`)
}

/** Who holds which office at the given date (default: today). */
/** The caller's own terms of office — self-service, any role. */
export async function listOwnFunctions() {
  return apiCall<MemberFunction[]>("/api/v1/members/me/functions")
}

export async function listFunctionHolders(at?: string) {
  const query = at ? `?at=${encodeURIComponent(at)}` : ""
  return apiCall<FunctionHolder[]>(`/api/v1/functions/holders${query}`)
}

/** The club's divisions, primary first. */
export async function listClubDivisions() {
  return apiCall<ClubDivision[]>("/api/v1/club/divisions")
}
