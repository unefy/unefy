"use client"

import { useMemo } from "react"
import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import { DateCell } from "@/components/ui/date-cell"
import type { AuditLogEntry } from "@/lib/types/admin"

function reasonOf(entry: AuditLogEntry): string | null {
  return typeof entry.payload?.reason === "string" ? entry.payload.reason : null
}

export function AuditLogTable({ entries }: { entries: AuditLogEntry[] }) {
  const t = useTranslations("admin.auditLog")
  const locale = useLocale()

  // The action list is data-driven: only actions actually present can be
  // filtered for, so the dropdown never offers an empty result.
  const actions = useMemo(
    () => [...new Set(entries.map((e) => e.action))].sort(),
    [entries]
  )

  const columns: DataTableColumn<AuditLogEntry>[] = [
    {
      key: "time",
      header: t("columns.time"),
      sortValue: (row) => row.created_at,
      cellClassName: "text-muted-foreground",
      cell: (row) => <DateCell value={row.created_at} />,
    },
    {
      key: "action",
      header: t("columns.action"),
      sortValue: (row) => row.action,
      cell: (row) => (
        <Badge variant="outline" className="font-mono text-xs">
          {row.action}
        </Badge>
      ),
    },
    {
      key: "actor",
      header: t("columns.actor"),
      sortValue: (row) => row.impersonator_email ?? row.actor_email,
      cell: (row) =>
        // When impersonating, the acting admin is the one that matters — show
        // them first and the borrowed identity underneath.
        row.impersonator_email ? (
          <>
            <div className="font-medium">{row.impersonator_email}</div>
            <div className="text-xs text-muted-foreground">
              {t("actingAs", { user: row.actor_email ?? "—" })}
            </div>
          </>
        ) : (
          <span className="font-medium">{row.actor_email ?? "—"}</span>
        ),
    },
    {
      key: "reason",
      header: t("columns.reason"),
      // The free-text column absorbs the leftover width and wraps, which keeps
      // the table inside the viewport instead of forcing a scrollbar.
      wrap: true,
      cellClassName: "text-muted-foreground",
      cell: (row) => reasonOf(row) ?? "—",
    },
    {
      key: "ip",
      header: t("columns.ip"),
      sortValue: (row) => row.ip_address,
      cellClassName: "font-mono text-xs text-muted-foreground",
      cell: (row) => row.ip_address ?? "—",
    },
  ]

  return (
    <DataTable
      data={entries}
      columns={columns}
      rowKey={(row) => row.id}
      locale={locale}
      defaultSort={{ key: "time", direction: "desc" }}
      searchPlaceholder={t("searchPlaceholder")}
      searchFields={(row) => [
        row.action,
        row.actor_email,
        row.impersonator_email,
        reasonOf(row),
      ]}
      filters={[
        {
          key: "action",
          allLabel: t("filters.allActions"),
          width: "w-56",
          options: actions.map((action) => ({
            value: action,
            label: action,
          })),
          matches: (row, value) => row.action === value,
        },
      ]}
      emptyText={t("empty")}
    />
  )
}
