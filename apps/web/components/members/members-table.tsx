"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useTranslations, useLocale } from "next-intl"
import type {
  ColumnOrderState,
  RowSelectionState,
  SortingState,
  VisibilityState,
} from "@tanstack/react-table"
import {
  useMembers,
  useBulkDeleteMembers,
} from "@/hooks/use-members"
import { useDebounce } from "@/hooks/use-debounce"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { toast } from "sonner"
import { useErrorMessage } from "@/lib/errors"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Delete02Icon,
  ArrowLeft01Icon,
  ArrowRight01Icon,
} from "@hugeicons/core-free-icons"
import { useClub } from "@/hooks/use-club"
import { getStatusLabel, parseMemberStatuses } from "@/lib/types/club"
import { DataTable } from "@/components/common/data-table"
import { ConfirmDialog } from "@/components/common/confirm-dialog"
import {
  ColumnSettings,
  type ColumnSettingsColumn,
} from "@/components/common/column-settings"
import { buildMembersColumns } from "@/components/members/members-columns"
import type { Member } from "@/lib/types/member"

const STORAGE_KEY = "unefy:members-table:columns"

interface PersistedColumnState {
  visibility: VisibilityState
  order: ColumnOrderState
}

const EMPTY_COLUMN_STATE: PersistedColumnState = { visibility: {}, order: [] }

function isPersistedColumnState(value: unknown): value is PersistedColumnState {
  if (typeof value !== "object" || value === null) return false
  const v = value as Record<string, unknown>
  if (
    typeof v.visibility !== "object" ||
    v.visibility === null ||
    Array.isArray(v.visibility)
  ) {
    return false
  }
  if (!Array.isArray(v.order)) return false
  const visibility = v.visibility as Record<string, unknown>
  for (const key of Object.keys(visibility)) {
    if (typeof visibility[key] !== "boolean") return false
  }
  return v.order.every((item) => typeof item === "string")
}

function usePersistedColumnState(): [
  PersistedColumnState,
  (next: Partial<PersistedColumnState>) => void,
] {
  const [state, setState] = useState<PersistedColumnState>(EMPTY_COLUMN_STATE)

  useEffect(() => {
    // Load persisted state on client mount. Initial render uses EMPTY_COLUMN_STATE
    // so server and client hydrate to the same output before the effect runs.
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return
      const parsed: unknown = JSON.parse(raw)
      if (isPersistedColumnState(parsed)) {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setState(parsed)
      } else {
        // Invalid shape — clear the corrupted entry so we stop re-reading it.
        localStorage.removeItem(STORAGE_KEY)
      }
    } catch {
      // localStorage unavailable or parse error — fall back to defaults.
    }
  }, [])

  function update(next: Partial<PersistedColumnState>) {
    setState((prev) => {
      const merged = { ...prev, ...next }
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(merged))
      } catch {
        // Storage quota exceeded or disabled — state stays in memory.
      }
      return merged
    })
  }

  return [state, update]
}

interface MembersTableProps {
  selectedId: string | null
  onSelect: (id: string | null) => void
}

export function MembersTable({ selectedId, onSelect }: MembersTableProps) {
  const t = useTranslations("members")
  const tc = useTranslations("common")
  const locale = useLocale()

  const { data: club } = useClub()
  const memberStatuses = parseMemberStatuses(club?.member_statuses ?? null)

  const router = useRouter()
  const searchParams = useSearchParams()
  const bulkDelete = useBulkDeleteMembers()

  const page = Number(searchParams.get("page")) || 1
  const status = searchParams.get("status") || ""
  const [searchInput, setSearchInput] = useState(
    searchParams.get("search") || "",
  )
  const search = useDebounce(searchInput, 300)

  const [sorting, setSorting] = useState<SortingState>([])
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({})
  const [confirmBulkDelete, setConfirmBulkDelete] = useState(false)
  const [persistedColumns, updatePersistedColumns] = usePersistedColumnState()
  const getErrorMessage = useErrorMessage()

  const columns = useMemo(
    () => buildMembersColumns({ t, memberStatuses, locale }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [locale, club?.member_statuses],
  )

  // Derive the backend sort field from the column's meta.sortField so we
  // don't have to maintain a parallel mapping.
  const activeSort = sorting[0]
  const sortField = useMemo(() => {
    if (!activeSort) return undefined
    const column = columns.find(
      (c) => ("accessorKey" in c && c.accessorKey === activeSort.id) ||
        c.id === activeSort.id,
    )
    return column?.meta?.sortField ?? activeSort.id
  }, [activeSort, columns])
  const sortOrder = activeSort ? (activeSort.desc ? "desc" : "asc") : undefined

  const { data, isLoading, error } = useMembers({
    page,
    per_page: 20,
    status: status || undefined,
    search: search || undefined,
    sort_by: sortField,
    sort_order: sortOrder,
  })

  const updateParams = useMemo(
    () => (updates: Record<string, string | null>) => {
      const params = new URLSearchParams(searchParams.toString())
      Object.entries(updates).forEach(([key, value]) => {
        if (value === null || value === "") {
          params.delete(key)
        } else {
          params.set(key, value)
        }
      })
      if (!("page" in updates)) params.delete("page")
      router.replace(`/members?${params.toString()}`, { scroll: false })
    },
    [router, searchParams],
  )

  // Sync debounced search into URL (avoids writing on every keystroke).
  useEffect(() => {
    const current = searchParams.get("search") || ""
    if (current === search) return
    updateParams({ search: search || null })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search])

  const members = data?.data || []
  const meta = data?.meta
  const statusCounts = meta?.status_counts ?? {}
  const totalCount = Object.values(statusCounts).reduce((a, b) => a + b, 0)

  const statusFilterItems = [
    { value: "all", label: `${t("allStatuses")} (${totalCount})` },
    ...memberStatuses.map((s) => ({
      value: s.key,
      label: `${getStatusLabel(s, t)} (${statusCounts[s.key] ?? 0})`,
    })),
  ]

  const settingsColumns: ColumnSettingsColumn[] = useMemo(
    () => [
      { id: "member_number", label: t("memberNumber") },
      { id: "first_name", label: t("firstName") },
      { id: "last_name", label: t("lastName") },
      { id: "email", label: t("email") },
      { id: "status", label: t("status") },
      { id: "joined_at", label: t("joinedAt") },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [locale],
  )

  const selectedIds = Object.keys(rowSelection).filter((k) => rowSelection[k])
  const selectionCount = selectedIds.length

  async function handleBulkDelete() {
    if (!selectionCount) return
    try {
      await bulkDelete.mutateAsync(selectedIds)
      toast.success(tc("saved"))
      setRowSelection({})
      setConfirmBulkDelete(false)
      if (selectedId && selectedIds.includes(selectedId)) onSelect(null)
    } catch (err) {
      toast.error(getErrorMessage(err))
    }
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-3">
        <Input
          placeholder={t("searchPlaceholder")}
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className="max-w-sm"
        />
        <Select
          items={statusFilterItems}
          value={status || "all"}
          onValueChange={(v) =>
            updateParams({ status: v === "all" ? null : v })
          }
        >
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {statusFilterItems.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="ml-auto flex items-center gap-2">
          {selectionCount > 0 && (
            <>
              <span className="text-muted-foreground text-sm">
                {t("nSelected", { count: selectionCount })}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConfirmBulkDelete(true)}
                disabled={bulkDelete.isPending}
              >
                <HugeiconsIcon icon={Delete02Icon} size={14} />
                {tc("delete")}
              </Button>
            </>
          )}
          <ColumnSettings
            columns={settingsColumns}
            columnVisibility={persistedColumns.visibility}
            onVisibilityChange={(v) => updatePersistedColumns({ visibility: v })}
            triggerLabel={tc("columns")}
          />
        </div>
      </div>

      {/* Table */}
      <DataTable<Member>
        columns={columns}
        data={members}
        isLoading={isLoading}
        error={error ?? null}
        errorStateText={tc("error")}
        sorting={sorting}
        onSortingChange={setSorting}
        rowSelection={rowSelection}
        onRowSelectionChange={setRowSelection}
        columnVisibility={persistedColumns.visibility}
        onColumnVisibilityChange={(v) => updatePersistedColumns({ visibility: v })}
        columnOrder={
          persistedColumns.order.length > 0
            ? ["select", ...persistedColumns.order.filter((id) => id !== "select")]
            : []
        }
        onColumnOrderChange={(o) =>
          updatePersistedColumns({ order: o.filter((id) => id !== "select") })
        }
        lockedColumnIds={["select"]}
        getRowId={(row) => row.id}
        onRowClick={(row) => onSelect(row.id)}
        isRowSelected={(row) => row.id === selectedId}
        emptyState={
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <p className="text-lg font-medium">{t("noMembers")}</p>
            <p className="text-muted-foreground mt-1 text-sm">
              {t("noMembersDescription")}
            </p>
          </div>
        }
      />

      <ConfirmDialog
        open={confirmBulkDelete}
        onOpenChange={setConfirmBulkDelete}
        title={t("deleteMember")}
        description={t("deleteConfirmBulk", { count: selectionCount })}
        destructive
        pending={bulkDelete.isPending}
        onConfirm={handleBulkDelete}
      />

      {/* Pagination */}
      {meta && meta.total_pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-muted-foreground text-sm">
            {meta.total} {t("title").toLowerCase()}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="icon-sm"
              disabled={page <= 1}
              onClick={() => updateParams({ page: String(page - 1) })}
              aria-label={tc("previous")}
            >
              <HugeiconsIcon icon={ArrowLeft01Icon} size={14} />
            </Button>
            <span className="flex items-center px-2 text-sm">
              {page} / {meta.total_pages}
            </span>
            <Button
              variant="outline"
              size="icon-sm"
              disabled={page >= meta.total_pages}
              onClick={() => updateParams({ page: String(page + 1) })}
              aria-label={tc("next")}
            >
              <HugeiconsIcon icon={ArrowRight01Icon} size={14} />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
