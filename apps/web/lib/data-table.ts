import type { ReactNode } from "react"

/**
 * The data side of `DataTable` — types plus the search, filter and sort
 * pipeline, with no React in sight.
 *
 * Separate from the component so this logic can be unit-tested. It is the most
 * reused code in the app and the easiest place for a silent mistake: a row
 * quietly filtered away, or a sort order that only looks right for the sample
 * data on screen.
 */

export type SortValue = string | number | boolean | null | undefined

export type SortState = { key: string; direction: "asc" | "desc" }

/** Sentinel for "filter not set" — Select does not allow an empty value. */
export const ALL = "all"

export type DataTableColumn<T> = {
  key: string
  header: ReactNode
  cell: (row: T) => ReactNode
  /** Without sortValue the column is not sortable. */
  sortValue?: (row: T) => SortValue
  align?: "left" | "center" | "right"
  /** Extra classes for this column's cells. */
  cellClassName?: string
  /**
   * Element next to the header that is NOT part of the sort target — an info
   * tip, say. It belongs here rather than in `header`, because `header` sits
   * inside a <button> on sortable columns and nested buttons are invalid HTML.
   */
  headerExtra?: ReactNode
  /**
   * Let this column's content wrap instead of staying on one line. Use it for
   * the one free-text column that would otherwise force the table to scroll.
   */
  wrap?: boolean
  /**
   * Collapse the column to its own content width instead of letting the table
   * layout stretch it. Use it for numbers and action buttons, so the value
   * stays next to its heading rather than drifting across an inflated column.
   *
   * Deliberately separate from `align`: how a column is aligned and how wide
   * it is are different questions, and tying them together meant a centred
   * number column silently lost its width.
   */
  shrink?: boolean
}

export type DataTableFilter<T> = {
  key: string
  /** Label of the "All …" option, e.g. "All statuses". */
  allLabel: string
  options: readonly { value: string; label: string }[]
  /** Width of the trigger, defaults to w-44. */
  width?: string
} & (
  | {
      /** Client filter: the table filters by itself. */
      matches: (row: T, value: string) => boolean
      value?: never
      onValueChange?: never
    }
  | {
      /**
       * Controlled filter: the page holds the value and filters itself —
       * server-side while loading, or because a start value other than "All"
       * is needed. The table filters nothing but still renders the select.
       */
      matches?: never
      value: string
      onValueChange: (value: string) => void
    }
)

/** Empty values always sort last, regardless of direction. */
export function isEmpty(value: SortValue): boolean {
  return value === null || value === undefined || value === ""
}

export function compare(a: SortValue, b: SortValue, locale: string): number {
  if (typeof a === "number" && typeof b === "number") return a - b
  if (typeof a === "boolean" && typeof b === "boolean") {
    return Number(a) - Number(b)
  }
  return String(a).localeCompare(String(b), locale)
}

/** Current value of a filter — controlled (server) or internal (client). */
export function filterValue<T>(
  filter: DataTableFilter<T>,
  internal: Record<string, string>
): string {
  return filter.value ?? internal[filter.key] ?? ALL
}

export function applyFilters<T>(
  rows: T[],
  filters: DataTableFilter<T>[],
  internal: Record<string, string>
): T[] {
  let result = rows
  for (const filter of filters) {
    // Server filters already applied while loading.
    if (!filter.matches) continue
    const value = internal[filter.key] ?? ALL
    const { matches } = filter
    if (value !== ALL) result = result.filter((row) => matches(row, value))
  }
  return result
}

export function applySearch<T>(
  rows: T[],
  search: string,
  searchFields?: (row: T) => (string | null | undefined)[]
): T[] {
  const needle = search.trim().toLowerCase()
  if (!needle || !searchFields) return rows
  return rows.filter((row) =>
    searchFields(row).some((field) => field?.toLowerCase().includes(needle))
  )
}

export function applySort<T>(
  rows: T[],
  columns: DataTableColumn<T>[],
  sort: SortState | null,
  locale: string
): T[] {
  if (!sort) return rows
  const column = columns.find((c) => c.key === sort.key)
  if (!column?.sortValue) return rows

  const { sortValue } = column
  const factor = sort.direction === "asc" ? 1 : -1
  const filled: T[] = []
  const empty: T[] = []
  for (const row of rows) {
    ;(isEmpty(sortValue(row)) ? empty : filled).push(row)
  }
  filled.sort((a, b) => factor * compare(sortValue(a), sortValue(b), locale))
  return [...filled, ...empty]
}

/** Filter, then search, then sort — the order the table applies them in. */
export function computeRows<T>({
  data,
  columns,
  filters,
  filterValues,
  search,
  searchFields,
  sort,
  locale,
}: {
  data: T[]
  columns: DataTableColumn<T>[]
  filters: DataTableFilter<T>[]
  filterValues: Record<string, string>
  search: string
  searchFields?: (row: T) => (string | null | undefined)[]
  sort: SortState | null
  locale: string
}): T[] {
  const filtered = applyFilters(data, filters, filterValues)
  const searched = applySearch(filtered, search, searchFields)
  return applySort(searched, columns, sort, locale)
}

/** Clicking a column: same column flips direction, a new one starts ascending. */
export function nextSort(current: SortState | null, key: string): SortState {
  return current?.key === key
    ? { key, direction: current.direction === "asc" ? "desc" : "asc" }
    : { key, direction: "asc" }
}
