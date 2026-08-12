import { apiCall } from "@/lib/api"
import type { AnnualReport } from "@/lib/types/reports"

/**
 * The annual figures, in one call.
 *
 * Board and above; the backend answers 403 for anyone else and the page turns
 * that into `notFound()`. Without a year the backend picks the club's current
 * one — computed in the club's own zone, which is not always the server's.
 */
export async function getAnnualReport(year?: number) {
  const query = year ? `?year=${year}` : ""
  return apiCall<AnnualReport>(`/api/v1/reports/annual${query}`)
}
