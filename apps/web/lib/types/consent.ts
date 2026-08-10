export type ConsentKind = "photos" | "newsletter" | "directory"

/** One row of the ledger — an answer at a moment. */
export type ConsentEntry = {
  id: string
  kind: ConsentKind
  granted: boolean
  recorded_at: string
  source: "application" | "self" | "board"
  note: string | null
}

/**
 * The current answer for one kind.
 *
 * `granted` is null when the member was never asked, which is not the same as
 * a refusal — the UI has to keep the two apart.
 */
export type ConsentState = {
  kind: ConsentKind
  granted: boolean | null
  since: string | null
  source: ConsentEntry["source"] | null
}

export type ConsentOverview = {
  current: ConsentState[]
  history: ConsentEntry[]
}
