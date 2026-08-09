"use client"

import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import {
  DataTable,
  type DataTableColumn,
  type DataTableFilter,
} from "@/components/ui/data-table"
import { formatDate, formatTime } from "@/lib/time"
import { EVENT_TYPE_KEYS, type ClubEvent } from "@/lib/types/event"
import { CheckIcon, TrophyIcon, XIcon } from "lucide-react"

/** "Upcoming" is measured against the load time, not against a render. */
function isUpcoming(event: ClubEvent, now: number): boolean {
  return new Date(event.ends_at ?? event.starts_at).getTime() >= now
}

export function EventsTable({
  events,
  timeZone,
  now,
}: {
  events: ClubEvent[]
  /** The club's zone — see `lib/time`. */
  timeZone: string
  /** Server-rendered timestamp, so server and client agree on "upcoming". */
  now: number
}) {
  const t = useTranslations("events")
  const locale = useLocale()
  const router = useRouter()

  const columns: DataTableColumn<ClubEvent>[] = [
    {
      key: "date",
      header: t("columns.date"),
      shrink: true,
      sortValue: (row) => row.starts_at,
      cell: (row) => formatDate(row.starts_at, locale, timeZone),
    },
    {
      key: "time",
      header: t("columns.time"),
      shrink: true,
      sortValue: (row) => row.starts_at,
      cellClassName: "text-muted-foreground tabular-nums",
      cell: (row) =>
        row.all_day
          ? t("allDay")
          : formatTime(row.starts_at, locale, timeZone) +
            (row.ends_at
              ? `–${formatTime(row.ends_at, locale, timeZone)}`
              : ""),
    },
    {
      key: "title",
      header: t("columns.title"),
      sortValue: (row) => row.title,
      cell: (row) => (
        <span className="flex items-center gap-2">
          <span className="font-medium">{row.title}</span>
          {row.competition_name && (
            <Badge variant="outline" className="gap-1">
              <TrophyIcon className="size-3" />
              {row.competition_name}
            </Badge>
          )}
          {row.status === "cancelled" && (
            <Badge variant="destructive">{t("status.cancelled")}</Badge>
          )}
        </span>
      ),
    },
    {
      key: "type",
      header: t("columns.type"),
      shrink: true,
      sortValue: (row) => t(`types.${row.event_type}`),
      cell: (row) => (
        <Badge variant="secondary">{t(`types.${row.event_type}`)}</Badge>
      ),
    },
    {
      key: "location",
      header: t("columns.location"),
      sortValue: (row) => row.location,
      cellClassName: "text-muted-foreground",
      cell: (row) => row.location ?? "—",
    },
    {
      key: "registrations",
      header: t("columns.registrations"),
      align: "right",
      shrink: true,
      sortValue: (row) => row.registered_count,
      cellClassName: "tabular-nums",
      cell: (row) =>
        row.registration_required
          ? row.max_participants
            ? `${row.registered_count}/${row.max_participants}`
            : String(row.registered_count)
          : "—",
    },
    {
      key: "self",
      header: t("columns.self"),
      align: "center",
      shrink: true,
      sortValue: (row) => row.is_registered,
      cell: (row) =>
        row.is_registered ? (
          <CheckIcon className="mx-auto size-4 text-primary" />
        ) : (
          <XIcon className="mx-auto size-4 text-muted-foreground/40" />
        ),
    },
  ]

  const filters: DataTableFilter<ClubEvent>[] = [
    {
      key: "timeframe",
      allLabel: t("filters.allTimeframes"),
      width: "w-40",
      options: [
        { value: "upcoming", label: t("filters.upcoming") },
        { value: "past", label: t("filters.past") },
      ],
      matches: (row, value) =>
        value === "upcoming" ? isUpcoming(row, now) : !isUpcoming(row, now),
    },
    {
      key: "type",
      allLabel: t("filters.allTypes"),
      options: EVENT_TYPE_KEYS.map((key) => ({
        value: key,
        label: t(`types.${key}`),
      })),
      matches: (row, value) => row.event_type === value,
    },
  ]

  return (
    <DataTable
      data={events}
      columns={columns}
      rowKey={(row) => row.id}
      onRowClick={(row) => router.push(`/events/${row.id}`)}
      searchPlaceholder={t("searchPlaceholder")}
      searchFields={(row) => [row.title, row.location, row.competition_name]}
      filters={filters}
      defaultSort={{ key: "date", direction: "desc" }}
      emptyText={t("empty")}
      locale={locale}
    />
  )
}
