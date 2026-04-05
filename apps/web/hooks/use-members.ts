import {
  useQuery,
  useMutation,
  useQueryClient,
  keepPreviousData,
} from "@tanstack/react-query"
import { apiFetch } from "@/lib/api-client"
import type {
  Member,
  MemberCreate,
  MemberUpdate,
  MemberListResponse,
} from "@/lib/types/member"

interface MemberListParams {
  page?: number
  per_page?: number
  status?: string
  category?: string
  search?: string
  sort_by?: string
  sort_order?: string
}

export const memberKeys = {
  all: ["members"] as const,
  list: (filters: MemberListParams) =>
    [...memberKeys.all, "list", filters] as const,
  detail: (id: string) => [...memberKeys.all, "detail", id] as const,
}

export function useMembers(params: MemberListParams = {}) {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.set(key, String(value))
    }
  })

  return useQuery({
    queryKey: memberKeys.list(params),
    queryFn: () =>
      apiFetch<MemberListResponse>(
        `/api/v1/members?${searchParams.toString()}`,
      ),
    placeholderData: keepPreviousData,
  })
}

export function useMember(id: string) {
  return useQuery({
    queryKey: memberKeys.detail(id),
    queryFn: async () => {
      const res = await apiFetch<{ data: Member }>(`/api/v1/members/${id}`)
      return res.data
    },
    enabled: !!id,
  })
}

export function useCreateMember() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: MemberCreate) => {
      const res = await apiFetch<{ data: Member }>("/api/v1/members", {
        method: "POST",
        body: JSON.stringify(data),
      })
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: memberKeys.all })
    },
  })
}

export function useUpdateMember() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: MemberUpdate }) => {
      const res = await apiFetch<{ data: Member }>(`/api/v1/members/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      })
      return res.data
    },
    onSuccess: (updatedMember) => {
      queryClient.setQueryData(
        memberKeys.detail(updatedMember.id),
        updatedMember,
      )
      queryClient.invalidateQueries({ queryKey: memberKeys.all })
    },
  })
}

export function useDeleteMember() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/api/v1/members/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: memberKeys.all })
    },
  })
}

export function useBulkDeleteMembers() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (ids: string[]) => {
      const res = await apiFetch<{ data: { deleted: number } }>(
        "/api/v1/members/bulk-delete",
        {
          method: "POST",
          body: JSON.stringify({ ids }),
        },
      )
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: memberKeys.all })
    },
  })
}
