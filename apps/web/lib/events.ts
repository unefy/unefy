import { apiCall, apiList } from "@/lib/api"
import type { ClubEvent, ClubEventDetail } from "@/lib/types/event"

/**
 * Server-side readers for events.
 *
 * Tenant scoping happens in the backend from the session — nothing here passes
 * a tenant id, so a caller cannot reach another club's calendar by construction.
 */

/** The list sorts and filters on the client, so it asks for one full page. */
export const EVENT_PAGE_SIZE = 100

export async function listEvents(
  options: { page?: number; perPage?: number; sortOrder?: "asc" | "desc" } = {}
) {
  const params = new URLSearchParams({
    page: String(options.page ?? 1),
    per_page: String(options.perPage ?? EVENT_PAGE_SIZE),
    sort_order: options.sortOrder ?? "desc",
  })
  return apiList<ClubEvent>(`/api/v1/events?${params}`)
}

export async function getEvent(eventId: string) {
  return apiCall<ClubEventDetail>(`/api/v1/events/${eventId}`)
}
