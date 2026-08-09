import { cookies } from "next/headers"

import { API_BASE, apiCall, apiList, sessionCookieHeader } from "@/lib/api"
import { SESSION_COOKIE } from "@/lib/constants"
import type {
  Competition,
  CompetitionEntry,
  CompetitionSession,
  Scoreboard,
  ScoreboardRow,
} from "@/lib/types/competition"

/**
 * Server-side readers for competitions.
 *
 * Tenant scoping happens in the backend from the session — nothing here passes
 * a tenant id, so a caller cannot reach another club's results by construction.
 */

/** The list sorts and filters on the client, so it asks for one full page. */
export const COMPETITION_PAGE_SIZE = 100

export async function listCompetitions() {
  return apiList<Competition>(
    `/api/v1/competitions?per_page=${COMPETITION_PAGE_SIZE}`
  )
}

export async function getCompetition(competitionId: string) {
  return apiCall<Competition>(`/api/v1/competitions/${competitionId}`)
}

export async function listCompetitionSessions(competitionId: string) {
  return (
    await apiList<CompetitionSession>(
      `/api/v1/competitions/${competitionId}/sessions?per_page=500`
    )
  ).data
}

export async function listEntries(competitionId: string, sessionId: string) {
  return (
    await apiList<CompetitionEntry>(
      `/api/v1/competitions/${competitionId}/sessions/${sessionId}/entries`
    )
  ).data
}

/**
 * The ranking, plus the scale it is measured on.
 *
 * Read by hand rather than through `apiCall`: this endpoint puts
 * `scoring_mode` and `scoring_unit` next to `data` instead of inside it, and
 * `apiCall` would throw both away — leaving the table unable to say whether a
 * low number is good.
 */
export async function getScoreboard(
  competitionId: string,
  discipline?: string
): Promise<Scoreboard> {
  const cookieStore = await cookies()
  const session = cookieStore.get(SESSION_COOKIE)?.value
  const query = discipline
    ? `?discipline=${encodeURIComponent(discipline)}`
    : ""

  const res = await fetch(
    `${API_BASE}/api/v1/competitions/${competitionId}/scoreboard${query}`,
    {
      headers: session ? sessionCookieHeader(session) : {},
      cache: "no-store",
    }
  )
  if (!res.ok) throw new Error(`scoreboard ${res.status}`)

  const body = (await res.json()) as {
    data?: ScoreboardRow[]
    scoring_mode?: string
    scoring_unit?: string
  }
  return {
    rows: body.data ?? [],
    scoring_mode: body.scoring_mode ?? "highest_wins",
    scoring_unit: body.scoring_unit ?? "",
  }
}
