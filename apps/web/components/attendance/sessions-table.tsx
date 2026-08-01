"use client"

import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import { formatDate, formatTime } from "@/lib/time"
import type { AttendanceSession } from "@/lib/types/attendance"
import { LockIcon } from "lucide-react"

export function SessionsTable({
  sessions,
  timeZone,
}: {
  sessions: AttendanceSession[]
  /** The club's zone — see `lib/time`. */
  timeZone: string
}) {
  const t = useTranslations("attendance")
  const locale = useLocale()
  const router = useRouter()

  const time = (value: string) => formatTime(value, locale, timeZone)

  const columns: DataTableColumn<AttendanceSession>[] = [
    {
      key: "opensAt",
      header: t("columns.date"),
      shrink: true,
      sortValue: (row) => row.opens_at,
      cell: (row) => formatDate(row.opens_at, locale, timeZone),
    },
    {
      key: "time",
      header: t("columns.time"),
      shrink: true,
      sortValue: (row) => row.opens_at,
      cellClassName: "text-muted-foreground tabular-nums",
      cell: (row) => `${time(row.opens_at)}–${time(row.closes_at)}`,
    },
    {
      key: "title",
      header: t("columns.title"),
      sortValue: (row) => row.title,
      cell: (row) => <span className="font-medium">{row.title}</span>,
    },
    {
      key: "location",
      header: t("columns.location"),
      sortValue: (row) => row.location,
      cellClassName: "text-muted-foreground",
      cell: (row) => row.location ?? "—",
    },
    {
      key: "supervisor",
      header: t("columns.supervisor"),
      sortValue: (row) => row.supervisor_name,
      cellClassName: "text-muted-foreground",
      cell: (row) => row.supervisor_name ?? "—",
    },
    {
      key: "recordCount",
      header: t("columns.present"),
      align: "center",
      shrink: true,
      sortValue: (row) => row.record_count,
      cellClassName: "tabular-nums",
      cell: (row) => row.record_count,
    },
    {
      key: "status",
      header: t("columns.status"),
      shrink: true,
      sortValue: (row) => row.status,
      cell: (row) =>
        row.status === "closed" ? (
          <Badge variant="secondary" className="gap-1">
            <LockIcon className="size-3" />
            {t("status.closed")}
          </Badge>
        ) : (
          <Badge variant="outline">{t("status.open")}</Badge>
        ),
    },
  ]

  return (
    <DataTable
      data={sessions}
      columns={columns}
      rowKey={(row) => row.id}
      locale={locale}
      defaultSort={{ key: "opensAt", direction: "desc" }}
      searchPlaceholder={t("searchPlaceholder")}
      searchFields={(row) => [row.title, row.location, row.supervisor_name]}
      filters={[
        {
          key: "status",
          allLabel: t("filters.allStatuses"),
          options: [
            { value: "open", label: t("status.open") },
            { value: "closed", label: t("status.closed") },
          ],
          matches: (row, value) => row.status === value,
        },
      ]}
      onRowClick={(row) => router.push(`/attendance/${row.id}`)}
      emptyText={t("empty")}
    />
  )
}
