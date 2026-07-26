import {
  useQuery,
  useMutation,
  useQueryClient,
  keepPreviousData,
} from "@tanstack/react-query"
import { apiFetch } from "@/lib/api-client"
import type {
  Due,
  DueListResponse,
  DueSummary,
  FeeType,
  FeeTypeCreate,
  FeeTypeUpdate,
  MemberFee,
  MemberFeeCreate,
} from "@/lib/types/due"

export interface DueListParams {
  page?: number
  per_page?: number
  status?: string
  member_id?: string
  year?: number
}

export const dueKeys = {
  all: ["dues"] as const,
  list: (filters: DueListParams) => [...dueKeys.all, "list", filters] as const,
  summary: (year?: number) => [...dueKeys.all, "summary", year] as const,
  feeTypes: ["fee-types"] as const,
  assignments: (memberId?: string) =>
    [...dueKeys.all, "assignments", memberId] as const,
}

// --- Fee types ---

export function useFeeTypes(includeInactive = false) {
  return useQuery({
    queryKey: [...dueKeys.feeTypes, includeInactive],
    queryFn: async () => {
      const res = await apiFetch<{ data: FeeType[] }>(
        `/api/v1/dues/fee-types?include_inactive=${includeInactive}`,
      )
      return res.data
    },
  })
}

export function useCreateFeeType() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: FeeTypeCreate) => {
      const res = await apiFetch<{ data: FeeType }>("/api/v1/dues/fee-types", {
        method: "POST",
        body: JSON.stringify(data),
      })
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dueKeys.feeTypes })
    },
  })
}

export function useUpdateFeeType() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: FeeTypeUpdate }) => {
      const res = await apiFetch<{ data: FeeType }>(
        `/api/v1/dues/fee-types/${id}`,
        { method: "PATCH", body: JSON.stringify(data) },
      )
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dueKeys.feeTypes })
    },
  })
}

export function useDeleteFeeType() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/api/v1/dues/fee-types/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dueKeys.feeTypes })
    },
  })
}

// --- Member fee assignments ---

export function useMemberFees(memberId: string) {
  return useQuery({
    queryKey: dueKeys.assignments(memberId),
    queryFn: async () => {
      const res = await apiFetch<{ data: MemberFee[] }>(
        `/api/v1/dues/assignments?member_id=${memberId}`,
      )
      return res.data
    },
    enabled: !!memberId,
  })
}

export function useAssignFee() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: MemberFeeCreate) => {
      const res = await apiFetch<{ data: MemberFee }>(
        "/api/v1/dues/assignments",
        { method: "POST", body: JSON.stringify(data) },
      )
      return res.data
    },
    onSuccess: (assignment) => {
      queryClient.invalidateQueries({
        queryKey: dueKeys.assignments(assignment.member_id),
      })
    },
  })
}

export function useRemoveAssignment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id }: { id: string; memberId: string }) =>
      apiFetch<void>(`/api/v1/dues/assignments/${id}`, { method: "DELETE" }),
    onSuccess: (_data, { memberId }) => {
      queryClient.invalidateQueries({
        queryKey: dueKeys.assignments(memberId),
      })
    },
  })
}

// --- Dues ---

export function useDues(params: DueListParams = {}) {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.set(key, String(value))
    }
  })

  return useQuery({
    queryKey: dueKeys.list(params),
    queryFn: () =>
      apiFetch<DueListResponse>(`/api/v1/dues?${searchParams.toString()}`),
    placeholderData: keepPreviousData,
  })
}

export function useDueSummary(year?: number) {
  return useQuery({
    queryKey: dueKeys.summary(year),
    queryFn: async () => {
      const query = year ? `?year=${year}` : ""
      const res = await apiFetch<{ data: DueSummary }>(
        `/api/v1/dues/summary${query}`,
      )
      return res.data
    },
  })
}

export function useGenerateDues() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (year: number) => {
      const res = await apiFetch<{ data: { created: number } }>(
        "/api/v1/dues/generate",
        { method: "POST", body: JSON.stringify({ year }) },
      )
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dueKeys.all })
    },
  })
}

interface PayDueInput {
  id: string
  paid_at?: string | null
  payment_method?: string | null
  note?: string | null
}

export function usePayDue() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...data }: PayDueInput) => {
      const res = await apiFetch<{ data: Due }>(`/api/v1/dues/${id}/pay`, {
        method: "POST",
        body: JSON.stringify(data),
      })
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dueKeys.all })
    },
  })
}

export function useCancelDue() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await apiFetch<{ data: Due }>(`/api/v1/dues/${id}/cancel`, {
        method: "POST",
      })
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dueKeys.all })
    },
  })
}

export function useReopenDue() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await apiFetch<{ data: Due }>(`/api/v1/dues/${id}/reopen`, {
        method: "POST",
      })
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dueKeys.all })
    },
  })
}
