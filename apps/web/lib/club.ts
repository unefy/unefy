import { apiCall } from "@/lib/api"
import type { Club } from "@/lib/types/club"

/**
 * Server-side reader for the club's own record.
 *
 * Tenant scoping happens in the backend from the session — nothing here names
 * a club, so a caller cannot reach another one by construction.
 */
export async function getClub() {
  return apiCall<Club>("/api/v1/club")
}
