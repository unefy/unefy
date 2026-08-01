"use client"

import { useMemo, useState, type ReactNode } from "react"
import { useTranslations } from "next-intl"

import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  ALL,
  computeRows,
  filterValue,
  nextSort,
  type DataTableColumn,
  type DataTableFilter,
  type SortState,
} from "@/lib/data-table"
import { cn } from "@/lib/utils"
import {
  ArrowDownIcon,
  ArrowUpIcon,
  ChevronsUpDownIcon,
  SearchIcon,
} from "lucide-react"

// Re-exported so callers keep importing the column type from the component
// they actually use.
export { ALL }
export type { DataTableColumn, DataTableFilter }

const ALIGN_CLASS = {
  left: "text-start",
  center: "text-center",
  right: "text-end",
} as const

/** Header blocks are flex containers, so they position by justify, not text-align. */
const JUSTIFY_CLASS = {
  left: "justify-start",
  center: "justify-center",
  right: "justify-end",
} as const

export function DataTable<T>({
  data,
  columns,
  rowKey,
  onRowClick,
  isRowSelected,
  searchPlaceholder,
  searchFields,
  filters = [],
  defaultSort,
  loading = false,
  emptyText,
  noMatchText,
  toolbarExtra,
  locale = "de",
}: {
  data: T[]
  columns: DataTableColumn<T>[]
  rowKey: (row: T) => string
  onRowClick?: (row: T) => void
  /** Highlights the active row — for master-detail pages. */
  isRowSelected?: (row: T) => boolean
  /** The search box only appears when searchFields is set. */
  searchPlaceholder?: string
  searchFields?: (row: T) => (string | null | undefined)[]
  filters?: DataTableFilter<T>[]
  defaultSort?: SortState
  loading?: boolean
  /** Shown when there is no data at all. */
  emptyText: ReactNode
  /** Shown when search/filters remove everything. */
  noMatchText?: ReactNode
  /** Extra controls on the right of the toolbar. */
  toolbarExtra?: ReactNode
  /** Collation locale for string sorting. */
  locale?: string
}) {
  const t = useTranslations("table")
  const [search, setSearch] = useState("")
  const [filterValues, setFilterValues] = useState<Record<string, string>>({})
  const [sort, setSort] = useState<SortState | null>(defaultSort ?? null)

  const filtered = useMemo(
    () =>
      computeRows({
        data,
        columns,
        filters,
        filterValues,
        search,
        searchFields,
        sort,
        locale,
      }),
    [data, columns, filters, filterValues, search, searchFields, sort, locale]
  )

  function toggleSort(key: string) {
    setSort((current) => nextSort(current, key))
  }

  function valueOf(filter: DataTableFilter<T>): string {
    return filterValue(filter, filterValues)
  }

  const hasToolbar = Boolean(searchFields) || filters.length > 0 || toolbarExtra
  const isFiltered =
    search.trim() !== "" || filters.some((f) => valueOf(f) !== ALL)

  return (
    <div className="space-y-4">
      {hasToolbar && (
        <div className="flex flex-wrap items-center gap-2">
          {searchFields && (
            <div className="relative">
              <SearchIcon className="pointer-events-none absolute start-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={searchPlaceholder ?? t("search")}
                className="w-64 ps-8"
              />
            </div>
          )}
          {filters.map((filter) => (
            <Select
              key={filter.key}
              value={valueOf(filter)}
              onValueChange={(value) =>
                filter.onValueChange
                  ? filter.onValueChange(String(value))
                  : setFilterValues((current) => ({
                      ...current,
                      [filter.key]: String(value),
                    }))
              }
            >
              <SelectTrigger className={filter.width ?? "w-44"}>
                {/*
                  base-ui's Select.Value renders the raw value, not the chosen
                  item's text (radix does the latter). Without this mapping the
                  trigger would read "all" instead of "All statuses".
                */}
                <SelectValue>
                  {(value: string) =>
                    value === ALL
                      ? filter.allLabel
                      : (filter.options.find((o) => o.value === value)?.label ??
                        filter.allLabel)
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value={ALL}>{filter.allLabel}</SelectItem>
                  {filter.options.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          ))}
          {toolbarExtra && <div className="ms-auto">{toolbarExtra}</div>}
        </div>
      )}

      {/*
        Tables only scroll inside their own frame — the page itself never
        scrolls sideways. `table-auto` plus a wrapping column keeps most
        tables inside the viewport so the scrollbar never appears.
      */}
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full table-auto text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              {columns.map((column) => {
                const align = ALIGN_CLASS[column.align ?? "left"]
                const active = sort?.key === column.key
                return (
                  <th
                    key={column.key}
                    className={cn(
                      "px-4 py-2.5 font-medium whitespace-nowrap",
                      // `w-0` on a nowrap cell in an auto table collapses the
                      // column to its own content width.
                      column.shrink && "w-0",
                      align
                    )}
                    aria-sort={
                      active
                        ? sort.direction === "asc"
                          ? "ascending"
                          : "descending"
                        : undefined
                    }
                  >
                    {/*
                      Block-level `flex`, never `inline-flex`: an inline box
                      takes its baseline from its first flex item, so a header
                      would sit at a different height depending on whether that
                      item is text or an icon. Filling the cell and positioning
                      with `justify-*` keeps every header on one line, whatever
                      it contains.

                      The label/icon order is the same in every column — only
                      the block's position changes with the alignment.
                    */}
                    <span
                      className={cn(
                        "flex items-center gap-1",
                        JUSTIFY_CLASS[column.align ?? "left"]
                      )}
                    >
                      {column.sortValue ? (
                        <button
                          type="button"
                          onClick={() => toggleSort(column.key)}
                          className={cn(
                            "flex items-center gap-1 hover:text-foreground",
                            !active && "text-muted-foreground"
                          )}
                        >
                          {column.header}
                          {!active ? (
                            <ChevronsUpDownIcon className="size-3.5 opacity-50" />
                          ) : sort.direction === "asc" ? (
                            <ArrowUpIcon className="size-3.5" />
                          ) : (
                            <ArrowDownIcon className="size-3.5" />
                          )}
                        </button>
                      ) : (
                        column.header
                      )}
                      {column.headerExtra}
                    </span>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {loading &&
              Array.from({ length: 5 }, (_, index) => (
                <tr key={index} className="border-b last:border-0">
                  {columns.map((column) => (
                    <td key={column.key} className="h-12 px-4 py-2">
                      <Skeleton className="h-5 w-full" />
                    </td>
                  ))}
                </tr>
              ))}

            {!loading &&
              filtered.map((row) => (
                <tr
                  key={rowKey(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  onKeyDown={
                    onRowClick
                      ? (e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault()
                            onRowClick(row)
                          }
                        }
                      : undefined
                  }
                  tabIndex={onRowClick ? 0 : undefined}
                  aria-selected={isRowSelected ? isRowSelected(row) : undefined}
                  className={cn(
                    "border-b transition-colors last:border-0",
                    onRowClick &&
                      "cursor-pointer hover:bg-muted/50 focus-visible:bg-muted/50 focus-visible:outline-none",
                    isRowSelected?.(row) && "bg-muted/70 hover:bg-muted/70"
                  )}
                >
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={cn(
                        // `h-12` acts as a minimum height in tables: rows stay
                        // equally tall across pages whether a cell holds text,
                        // a badge or an avatar. Taller content may still grow.
                        //
                        // `whitespace-nowrap` keeps cells on one line, so row
                        // height does not depend on column width. Long text is
                        // truncated per cell; a column marked `wrap` opts out
                        // and absorbs the remaining width instead.
                        "h-12 px-4 py-2",
                        column.wrap ? "min-w-48" : "whitespace-nowrap",
                        ALIGN_CLASS[column.align ?? "left"],
                        column.cellClassName
                      )}
                    >
                      {column.cell(row)}
                    </td>
                  ))}
                </tr>
              ))}

            {!loading && filtered.length === 0 && (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-8 text-center text-muted-foreground"
                >
                  {isFiltered ? (noMatchText ?? t("noMatch")) : emptyText}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
