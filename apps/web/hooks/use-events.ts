import {
  useQuery,
  useMutation,
  useQueryClient,
  keepPreviousData,
} from "@tanstack/react-query"
import { apiFetch } from "@/lib/api-client"
import type {
  ClubEvent,
  ClubEventDetail,
  EventCreate,
  EventListResponse,
  EventRegistration,
  EventUpdate,
} from "@/lib/types/event"

export interface EventListParams {
  page?: number
  per_page?: number
  event_type?: string
  starts_after?: string
  starts_before?: string
  competition_id?: string
  sort_order?: "asc" | "desc"
}

export const eventKeys = {
  all: ["events"] as const,
  list: (filters: EventListParams) =>
    [...eventKeys.all, "list", filters] as const,
  detail: (id: string) => [...eventKeys.all, "detail", id] as const,
}

export function useEvents(params: EventListParams = {}) {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.set(key, String(value))
    }
  })

  return useQuery({
    queryKey: eventKeys.list(params),
    queryFn: () =>
      apiFetch<EventListResponse>(`/api/v1/events?${searchParams.toString()}`),
    placeholderData: keepPreviousData,
  })
}

export function useEvent(id: string) {
  return useQuery({
    queryKey: eventKeys.detail(id),
    queryFn: async () => {
      const res = await apiFetch<{ data: ClubEventDetail }>(
        `/api/v1/events/${id}`,
      )
      return res.data
    },
    enabled: !!id,
  })
}

export function useCreateEvent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: EventCreate) => {
      const res = await apiFetch<{ data: ClubEvent }>("/api/v1/events", {
        method: "POST",
        body: JSON.stringify(data),
      })
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: eventKeys.all })
    },
  })
}

export function useUpdateEvent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: EventUpdate }) => {
      const res = await apiFetch<{ data: ClubEvent }>(`/api/v1/events/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      })
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: eventKeys.all })
    },
  })
}

export function useDeleteEvent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/api/v1/events/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: eventKeys.all })
    },
  })
}

export function useRegisterMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      eventId,
      memberId,
    }: {
      eventId: string
      memberId: string
    }) => {
      const res = await apiFetch<{ data: EventRegistration }>(
        `/api/v1/events/${eventId}/registrations`,
        { method: "POST", body: JSON.stringify({ member_id: memberId }) },
      )
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: eventKeys.all })
    },
  })
}

export function useUnregisterMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      eventId,
      registrationId,
    }: {
      eventId: string
      registrationId: string
    }) =>
      apiFetch<void>(`/api/v1/events/${eventId}/registrations/${registrationId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: eventKeys.all })
    },
  })
}
