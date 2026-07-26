export type CompetitionType = "league" | "competition" | "training"

export interface Competition {
  id: string
  name: string
  description: string | null
  competition_type: CompetitionType
  start_date: string
  end_date: string | null
  scoring_mode: "highest_wins" | "lowest_wins"
  scoring_unit: string
  disciplines: string[] | null
  created_at: string
  updated_at: string
}

export interface CompetitionSession {
  id: string
  competition_id: string
  name: string | null
  date: string
  location: string | null
  discipline: string | null
  event_id: string | null
  created_at: string
  updated_at: string
}

export interface CompetitionCreate {
  name: string
  description?: string | null
  competition_type: CompetitionType
  start_date: string
  end_date?: string | null
  scoring_mode: "highest_wins" | "lowest_wins"
  scoring_unit: string
  disciplines?: string[] | null
}

export type CompetitionUpdate = Partial<CompetitionCreate>

export interface SessionCreate {
  name?: string | null
  date: string
  location?: string | null
  discipline?: string | null
  create_calendar_event?: boolean
  starts_at?: string | null
}

export interface CompetitionEntry {
  id: string
  session_id: string
  member_id: string
  score_value: number
  score_unit: string
  discipline: string | null
  details: Record<string, unknown> | null
  source: string
  recorded_by: string | null
  recorded_at: string
  notes: string | null
  created_at: string
  updated_at: string
}

export interface EntryCreate {
  member_id: string
  score_value: number
  score_unit?: string
  discipline?: string | null
  recorded_at: string
  notes?: string | null
}

export interface EntryUpdate {
  score_value?: number
  notes?: string | null
}

export interface ScoreboardRow {
  member_id: string
  total_score: number
  entry_count: number
  average_score: number
  best_score: number
  rank: number
}

export interface ScoreboardResponse {
  data: ScoreboardRow[]
  scoring_mode: "highest_wins" | "lowest_wins"
  scoring_unit: string
}

export interface PaginatedMeta {
  total: number
  page: number
  per_page: number
  total_pages: number
}

export interface CompetitionListResponse {
  data: Competition[]
  meta: PaginatedMeta
}

export interface SessionListResponse {
  data: CompetitionSession[]
  meta: PaginatedMeta
}

export interface EntryListResponse {
  data: CompetitionEntry[]
  meta: PaginatedMeta
}
