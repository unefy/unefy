import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api-client"
import { eventKeys } from "@/hooks/use-events"
import type {
  Competition,
  CompetitionCreate,
  CompetitionEntry,
  CompetitionListResponse,
  CompetitionSession,
  CompetitionUpdate,
  EntryCreate,
  EntryListResponse,
  EntryUpdate,
  ScoreboardResponse,
  SessionCreate,
  SessionListResponse,
} from "@/lib/types/competition"

export const competitionKeys = {
  all: ["competitions"] as const,
  list: () => [...competitionKeys.all, "list"] as const,
  detail: (id: string) => [...competitionKeys.all, "detail", id] as const,
  sessions: (competitionId: string) =>
    [...competitionKeys.all, competitionId, "sessions"] as const,
  entries: (competitionId: string, sessionId: string) =>
    [
      ...competitionKeys.all,
      competitionId,
      "sessions",
      sessionId,
      "entries",
    ] as const,
  scoreboard: (competitionId: string) =>
    [...competitionKeys.all, competitionId, "scoreboard"] as const,
}

export function useCompetitions() {
  return useQuery({
    queryKey: competitionKeys.list(),
    queryFn: () =>
      apiFetch<CompetitionListResponse>("/api/v1/competitions?per_page=100"),
  })
}

export function useCompetition(id: string) {
  return useQuery({
    queryKey: competitionKeys.detail(id),
    queryFn: async () => {
      const res = await apiFetch<{ data: Competition }>(
        `/api/v1/competitions/${id}`
      )
      return res.data
    },
    enabled: !!id,
  })
}

export function useCreateCompetition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: CompetitionCreate) => {
      const res = await apiFetch<{ data: Competition }>(
        "/api/v1/competitions",
        {
          method: "POST",
          body: JSON.stringify(data),
        }
      )
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: competitionKeys.all })
    },
  })
}

export function useUpdateCompetition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string
      data: CompetitionUpdate
    }) => {
      const res = await apiFetch<{ data: Competition }>(
        `/api/v1/competitions/${id}`,
        { method: "PATCH", body: JSON.stringify(data) }
      )
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: competitionKeys.all })
    },
  })
}

export function useDeleteCompetition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/api/v1/competitions/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: competitionKeys.all })
    },
  })
}

export function useCompetitionSessions(competitionId: string) {
  return useQuery({
    queryKey: competitionKeys.sessions(competitionId),
    queryFn: () =>
      apiFetch<SessionListResponse>(
        `/api/v1/competitions/${competitionId}/sessions?per_page=500`
      ),
    enabled: !!competitionId,
  })
}

export function useCreateSession(competitionId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: SessionCreate) => {
      const res = await apiFetch<{ data: CompetitionSession }>(
        `/api/v1/competitions/${competitionId}/sessions`,
        { method: "POST", body: JSON.stringify(data) }
      )
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: competitionKeys.sessions(competitionId),
      })
      queryClient.invalidateQueries({ queryKey: eventKeys.all })
    },
  })
}

export function useSessionEntries(competitionId: string, sessionId: string) {
  return useQuery({
    queryKey: competitionKeys.entries(competitionId, sessionId),
    queryFn: () =>
      apiFetch<EntryListResponse>(
        `/api/v1/competitions/${competitionId}/sessions/${sessionId}/entries?per_page=500`
      ),
    enabled: !!competitionId && !!sessionId,
  })
}

export function useScoreboard(competitionId: string) {
  return useQuery({
    queryKey: competitionKeys.scoreboard(competitionId),
    queryFn: () =>
      apiFetch<ScoreboardResponse>(
        `/api/v1/competitions/${competitionId}/scoreboard`
      ),
    enabled: !!competitionId,
  })
}

function useInvalidateEntries(competitionId: string, sessionId: string) {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({
      queryKey: competitionKeys.entries(competitionId, sessionId),
    })
    queryClient.invalidateQueries({
      queryKey: competitionKeys.scoreboard(competitionId),
    })
  }
}

export function useCreateEntry(competitionId: string, sessionId: string) {
  const invalidate = useInvalidateEntries(competitionId, sessionId)
  return useMutation({
    mutationFn: async (data: EntryCreate) => {
      const res = await apiFetch<{ data: CompetitionEntry }>(
        `/api/v1/competitions/${competitionId}/sessions/${sessionId}/entries`,
        { method: "POST", body: JSON.stringify(data) }
      )
      return res.data
    },
    onSuccess: invalidate,
  })
}

export function useUpdateEntry(competitionId: string, sessionId: string) {
  const invalidate = useInvalidateEntries(competitionId, sessionId)
  return useMutation({
    mutationFn: async ({
      entryId,
      data,
    }: {
      entryId: string
      data: EntryUpdate
    }) => {
      const res = await apiFetch<{ data: CompetitionEntry }>(
        `/api/v1/competitions/${competitionId}/sessions/${sessionId}/entries/${entryId}`,
        { method: "PATCH", body: JSON.stringify(data) }
      )
      return res.data
    },
    onSuccess: invalidate,
  })
}

export function useDeleteEntry(competitionId: string, sessionId: string) {
  const invalidate = useInvalidateEntries(competitionId, sessionId)
  return useMutation({
    mutationFn: (entryId: string) =>
      apiFetch<void>(
        `/api/v1/competitions/${competitionId}/sessions/${sessionId}/entries/${entryId}`,
        { method: "DELETE" }
      ),
    onSuccess: invalidate,
  })
}

export function useDeleteSession(competitionId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (sessionId: string) =>
      apiFetch<void>(
        `/api/v1/competitions/${competitionId}/sessions/${sessionId}`,
        { method: "DELETE" }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: competitionKeys.sessions(competitionId),
      })
      queryClient.invalidateQueries({ queryKey: eventKeys.all })
    },
  })
}
