/**
 * The competition layer is sport-agnostic on purpose.
 *
 * A result is one number (`score_value`) in a unit the club names itself
 * (`scoring_unit`: Punkte, Ringe, Sekunden, Meter …), ranked by
 * `scoring_mode`. Anything sport-specific — rings, targets, calibres — lives
 * in `details` and belongs to the module that understands it, never here.
 */

/** Types a club can pick. `free_training` is machinery and never offered. */
export const COMPETITION_TYPE_KEYS = [
  "competition",
  "league",
  "training",
] as const

export type CompetitionType = (typeof COMPETITION_TYPE_KEYS)[number]

export const SCORING_MODE_KEYS = ["highest_wins", "lowest_wins"] as const

export type Competition = {
  id: string
  name: string
  description: string | null
  competition_type: string
  start_date: string
  end_date: string | null
  /** "highest_wins" for points and rings, "lowest_wins" for times. */
  scoring_mode: string
  /** The club's own word for the number, e.g. "Punkte" or "Sekunden". */
  scoring_unit: string
  disciplines: string[] | null
  created_at: string
  updated_at: string
}

/** One round of a competition — a match day, a leg, a training evening. */
export type CompetitionSession = {
  id: string
  competition_id: string
  name: string | null
  date: string
  location: string | null
  discipline: string | null
  /** Set when the round also sits in the calendar. */
  event_id: string | null
  created_at: string
  updated_at: string
}

/** One participant's result in a round. */
export type CompetitionEntry = {
  id: string
  session_id: string
  member_id: string
  score_value: number
  score_unit: string
  discipline: string | null
  details: Record<string, unknown> | null
  /** "manual" | "scan" — scan means it came from a device, not a keyboard. */
  source: string
  recorded_by: string | null
  recorded_at: string
  notes: string | null
}

/** A row of the ranking, as computed by the backend. */
export type ScoreboardRow = {
  member_id: string
  member_name: string
  total_score: number
  entry_count: number
  average_score: number
  best_score: number
  rank: number
}

/** The scoreboard response carries the competition's scale alongside the rows. */
export type Scoreboard = {
  rows: ScoreboardRow[]
  scoring_mode: string
  scoring_unit: string
}
