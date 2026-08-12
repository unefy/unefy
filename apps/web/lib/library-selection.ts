/**
 * Which documents are ticked, and what may be done to them.
 *
 * Pure, and separate from the view for one reason: a selection outlives the
 * list it was made in. The page reloads after every change, and an id that is
 * still ticked but no longer on screen is how a bulk delete reaches a document
 * nobody meant to touch.
 */

export type Selectable = { id: string }

/** Drop everything that is no longer in the list. */
export function pruneSelection(
  selected: ReadonlySet<string>,
  rows: readonly Selectable[]
): Set<string> {
  const present = new Set(rows.map((row) => row.id))
  return new Set([...selected].filter((id) => present.has(id)))
}

/** Tick or untick one row. */
export function toggleSelection(
  selected: ReadonlySet<string>,
  id: string
): Set<string> {
  const next = new Set(selected)
  if (!next.delete(id)) next.add(id)
  return next
}

/**
 * The header checkbox: all rows, or none.
 *
 * "All" means the rows currently on screen, which is why the table this is
 * used with does no filtering of its own — a select-all that quietly skips
 * hidden rows is worse than no select-all.
 */
export function toggleAll(
  selected: ReadonlySet<string>,
  rows: readonly Selectable[]
): Set<string> {
  return allSelected(selected, rows) ? new Set() : new Set(rows.map((r) => r.id))
}

export function allSelected(
  selected: ReadonlySet<string>,
  rows: readonly Selectable[]
): boolean {
  return rows.length > 0 && rows.every((row) => selected.has(row.id))
}
