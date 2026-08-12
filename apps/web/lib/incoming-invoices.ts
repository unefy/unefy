import { apiCall, apiList } from "@/lib/api"
import type {
  IncomingInvoice,
  IncomingInvoiceSummary,
} from "@/lib/types/incoming-invoices"

/**
 * Server-side readers for the incoming-invoice register.
 *
 * Board and above throughout; the backend answers 403 for anyone else and the
 * page turns that into `notFound()`.
 */

export const INVOICES_PAGE_SIZE = 100

export async function listIncomingInvoices(
  options: { year?: number; status?: string } = {}
) {
  const params = new URLSearchParams({ per_page: String(INVOICES_PAGE_SIZE) })
  if (options.year) params.set("year", String(options.year))
  if (options.status) params.set("status", options.status)
  return apiList<IncomingInvoice>(`/api/v1/incoming-invoices?${params}`)
}

export async function getIncomingInvoiceSummary(year?: number) {
  const query = year ? `?year=${year}` : ""
  return apiCall<IncomingInvoiceSummary>(
    `/api/v1/incoming-invoices/summary${query}`
  )
}

export async function getIncomingInvoice(id: string) {
  return apiCall<IncomingInvoice>(`/api/v1/incoming-invoices/${id}`)
}
