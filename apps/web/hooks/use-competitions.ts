import { useQuery } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api-client"
import type {
  CompetitionListResponse,
  SessionListResponse,
} from "@/lib/types/competition"

export const competitionKeys = {
  all: ["competitions"] as const,
  list: () => [...competitionKeys.all, "list"] as const,
  sessions: (competitionId: string) =>
    [...competitionKeys.all, competitionId, "sessions"] as const,
}

export function useCompetitions() {
  return useQuery({
    queryKey: competitionKeys.list(),
    queryFn: () =>
      apiFetch<CompetitionListResponse>("/api/v1/competitions?per_page=100"),
  })
}

export function useCompetitionSessions(competitionId: string) {
  return useQuery({
    queryKey: competitionKeys.sessions(competitionId),
    queryFn: () =>
      apiFetch<SessionListResponse>(
        `/api/v1/competitions/${competitionId}/sessions?per_page=500`,
      ),
    enabled: !!competitionId,
  })
}
