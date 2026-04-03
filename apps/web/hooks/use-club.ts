import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api-client"
import type { Club } from "@/lib/types/club"

export const clubKeys = {
  all: ["club"] as const,
  detail: () => [...clubKeys.all, "detail"] as const,
}

export function useClub() {
  return useQuery({
    queryKey: clubKeys.detail(),
    queryFn: () => apiFetch<Club>("/api/v1/club"),
  })
}

export function useUpdateClub() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: Partial<Club>) =>
      apiFetch<Club>("/api/v1/club", {
        method: "PATCH",
        body: JSON.stringify(
          Object.fromEntries(
            Object.entries(data).map(([k, v]) => [
              k,
              typeof v === "boolean" ? v : v === "" ? null : v,
            ]),
          ),
        ),
      }),
    onSuccess: (updatedClub) => {
      queryClient.setQueryData(clubKeys.detail(), updatedClub)
    },
  })
}
