/** Types for club functions (Ämter) — kept in sync with app/schemas/function.py. */

export type FunctionLevel = "club" | "division"

export type SuggestedRole = "owner" | "admin" | "board" | "member"

/** A club-owned office, e.g. "1. Vorsitzende:r". */
export type ClubFunction = {
  id: string
  name: string
  level: FunctionLevel
  suggested_role: SuggestedRole | null
  sort_order: number
  is_active: boolean
  created_at: string
  updated_at: string
}

/** One term of office of a member. `valid_to === null` = currently in office. */
export type MemberFunction = {
  id: string
  member_id: string
  function_id: string
  function_name: string
  level: FunctionLevel
  division_id: string | null
  division_name: string | null
  valid_from: string
  valid_to: string | null
  note: string | null
  created_at: string
  updated_at: string
}

/** A row of the board list (who holds which office at a date). */
export type FunctionHolder = {
  assignment_id: string
  function_id: string
  function_name: string
  level: FunctionLevel
  sort_order: number
  division_id: string | null
  division_name: string | null
  member_id: string
  member_first_name: string
  member_last_name: string
  valid_from: string
  valid_to: string | null
  note: string | null
}

/** A club division (Sparte), primary first. */
export type ClubDivision = {
  id: string
  name: string
  is_primary: boolean
  /** The sport it practises — what makes a division more than a label. */
  sport_id: string | null
}
