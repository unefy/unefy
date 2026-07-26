"use client"

import { useMemo } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useTranslations, useLocale } from "next-intl"
import type { ColumnDef } from "@tanstack/react-table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DataTable } from "@/components/common/data-table"
import { useEvents } from "@/hooks/use-events"
import { formatDate } from "@/lib/date"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowLeft01Icon, ArrowRight01Icon } from "@hugeicons/core-free-icons"
import type { ClubEvent } from "@/lib/types/event"

interface EventsTableProps {
  scope: "upcoming" | "past"
  selectedId: string | null
  onSelect: (id: string | null) => void
}

export function EventsTable({ scope, selectedId, onSelect }: EventsTableProps) {
  const t = useTranslations("events")
  const tc = useTranslations("common")
  const locale = useLocale()
  const router = useRouter()
  const searchParams = useSearchParams()

  const page = Number(searchParams.get("page")) || 1
  const now = useMemo(() => new Date().toISOString(), [])

  const { data, isLoading, error } = useEvents({
    page,
    per_page: 20,
    ...(scope === "upcoming"
      ? { starts_after: now, sort_order: "asc" as const }
      : { starts_before: now, sort_order: "desc" as const }),
  })

  const columns = useMemo<ColumnDef<ClubEvent>[]>(
    () => [
      {
        accessorKey: "starts_at",
        size: 140,
        header: t("date"),
        enableSorting: false,
        cell: ({ row }) => {
          const event = row.original
          const time = event.all_day
            ? t("allDay")
            : new Date(event.starts_at).toLocaleTimeString(locale, {
                hour: "2-digit",
                minute: "2-digit",
              })
          return (
            <div>
              <p className="font-medium">{formatDate(event.starts_at, locale)}</p>
              <p className="text-muted-foreground text-xs">{time}</p>
            </div>
          )
        },
      },
      {
        accessorKey: "title",
        size: 220,
        header: t("eventTitle"),
        enableSorting: false,
        cell: ({ row }) => (
          <div className="flex items-center gap-2">
            <span className="font-medium">{row.original.title}</span>
            {row.original.status === "cancelled" && (
              <Badge variant="outline">{t("status_cancelled")}</Badge>
            )}
          </div>
        ),
      },
      {
        accessorKey: "event_type",
        size: 130,
        header: t("type"),
        enableSorting: false,
        cell: ({ getValue }) => (
          <Badge variant="secondary">{t(`type_${getValue<string>()}`)}</Badge>
        ),
      },
      {
        accessorKey: "location",
        size: 180,
        header: t("location"),
        enableSorting: false,
        cell: ({ getValue }) => (
          <span className="text-muted-foreground">
            {getValue<string | null>() || "—"}
          </span>
        ),
        meta: {
          headerClassName: "hidden md:table-cell",
          cellClassName: "hidden md:table-cell",
        },
      },
      {
        accessorKey: "registered_count",
        size: 120,
        header: t("registrations"),
        enableSorting: false,
        cell: ({ row }) => {
          const event = row.original
          if (!event.registration_required && event.registered_count === 0) {
            return <span className="text-muted-foreground">—</span>
          }
          return (
            <span className="tabular-nums">
              {event.registered_count}
              {event.max_participants ? ` / ${event.max_participants}` : ""}
            </span>
          )
        },
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [locale],
  )

  function updateParams(updates: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams.toString())
    Object.entries(updates).forEach(([key, value]) => {
      if (value === null || value === "") {
        params.delete(key)
      } else {
        params.set(key, value)
      }
    })
    router.replace(`/events?${params.toString()}`, { scroll: false })
  }

  const events = data?.data || []
  const meta = data?.meta

  return (
    <div className="space-y-4">
      <DataTable<ClubEvent>
        columns={columns}
        data={events}
        isLoading={isLoading}
        error={error ?? null}
        errorStateText={tc("error")}
        getRowId={(row) => row.id}
        onRowClick={(row) => onSelect(row.id)}
        isRowSelected={(row) => row.id === selectedId}
        emptyState={
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <p className="text-lg font-medium">{t("noEvents")}</p>
            <p className="text-muted-foreground mt-1 text-sm">
              {t("noEventsDescription")}
            </p>
          </div>
        }
      />

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
