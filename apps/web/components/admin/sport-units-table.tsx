"use client"

import { type ReactNode } from "react"
import { useLocale, useTranslations } from "next-intl"

import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import type { CatalogUnit } from "@/lib/types/admin"

export function SportUnitsTable({
  units,
  actions,
}: {
  units: CatalogUnit[]
  /**
   * Row actions rendered on the server, keyed by unit id. They close over
   * server actions, which only a Server Component can create.
   */
  actions: Record<string, ReactNode>
}) {
  const t = useTranslations("admin.sportDetail")
  const locale = useLocale()

  const columns: DataTableColumn<CatalogUnit>[] = [
    {
      key: "name",
      header: t("columns.name"),
      sortValue: (row) => row.name,
      cell: (row) => <span className="font-medium">{row.name}</span>,
    },
    {
      key: "symbol",
      header: t("columns.symbol"),
      sortValue: (row) => row.symbol,
      cellClassName: "text-muted-foreground",
      cell: (row) => row.symbol ?? "—",
    },
    {
      key: "sortOrder",
      header: t("columns.sortOrder"),
      align: "center",
      shrink: true,
      sortValue: (row) => row.sort_order,
      cellClassName: "text-muted-foreground tabular-nums",
      cell: (row) => row.sort_order,
    },
    {
      key: "actions",
      header: "",
      align: "right",
      shrink: true,
      cell: (row) => <div className="flex justify-end">{actions[row.id]}</div>,
    },
  ]

  return (
    <DataTable
      data={units}
      columns={columns}
      rowKey={(row) => row.id}
      locale={locale}
      // Units carry an explicit order that the club sees, so that is the
      // default view rather than alphabetical.
      defaultSort={{ key: "sortOrder", direction: "asc" }}
      emptyText={t("noUnits")}
    />
  )
}
