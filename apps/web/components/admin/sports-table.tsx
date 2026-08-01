"use client"

import { type ReactNode } from "react"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import type { Sport } from "@/lib/types/admin"

export function SportsTable({
  sports,
  actions,
}: {
  sports: Sport[]
  /**
   * Row actions rendered on the server, keyed by sport id. They close over
   * server actions, so they cannot be constructed here — the page passes them
   * in as ready-made nodes.
   */
  actions: Record<string, ReactNode>
}) {
  const t = useTranslations("admin.sports")
  const locale = useLocale()
  const router = useRouter()

  const columns: DataTableColumn<Sport>[] = [
    {
      key: "name",
      header: t("columns.name"),
      sortValue: (row) => row.name,
      cell: (row) => <span className="font-medium">{row.name}</span>,
    },
    {
      key: "key",
      header: t("columns.key"),
      sortValue: (row) => row.key,
      cellClassName: "font-mono text-xs text-muted-foreground",
      cell: (row) => row.key,
    },
    {
      key: "modules",
      header: t("columns.modules"),
      cell: (row) =>
        row.modules.length === 0 ? (
          <span className="text-muted-foreground">—</span>
        ) : (
          <div className="flex flex-wrap gap-1">
            {row.modules.map((module) => (
              <Badge key={module} variant="secondary">
                {module}
              </Badge>
            ))}
          </div>
        ),
    },
    {
      key: "units",
      header: t("columns.units"),
      align: "center",
      shrink: true,
      sortValue: (row) => row.unit_count,
      cellClassName: "tabular-nums",
      cell: (row) => row.unit_count,
    },
    {
      key: "disciplines",
      header: t("columns.disciplines"),
      align: "center",
      shrink: true,
      sortValue: (row) => row.discipline_count,
      cellClassName: "tabular-nums",
      cell: (row) => row.discipline_count,
    },
    {
      key: "status",
      header: t("columns.status"),
      sortValue: (row) => row.is_active,
      cell: (row) => (
        <Badge variant={row.is_active ? "secondary" : "outline"}>
          {row.is_active ? t("active") : t("inactive")}
        </Badge>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      shrink: true,
      // Stops a click on edit/delete from also opening the detail page.
      cell: (row) => (
        <div
          className="flex justify-end"
          onClick={(event) => event.stopPropagation()}
        >
          {actions[row.id]}
        </div>
      ),
    },
  ]

  return (
    <DataTable
      data={sports}
      columns={columns}
      rowKey={(row) => row.id}
      locale={locale}
      defaultSort={{ key: "name", direction: "asc" }}
      searchPlaceholder={t("searchPlaceholder")}
      searchFields={(row) => [row.name, row.key]}
      filters={[
        {
          key: "status",
          allLabel: t("filters.allStatuses"),
          options: [
            { value: "active", label: t("active") },
            { value: "inactive", label: t("inactive") },
          ],
          matches: (row, value) => row.is_active === (value === "active"),
        },
      ]}
      onRowClick={(row) => router.push(`/admin/sports/${row.id}`)}
      emptyText={t("empty")}
    />
  )
}
