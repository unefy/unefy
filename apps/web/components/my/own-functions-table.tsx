"use client"

import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import { formatDate } from "@/lib/time"
import type { MemberFunction } from "@/lib/types/functions"

/** A member's own offices. Past terms stay — they are the person's history. */
export function OwnFunctionsTable({
  functions,
}: {
  functions: MemberFunction[]
}) {
  const t = useTranslations("my.functions")
  const locale = useLocale()

  const columns: DataTableColumn<MemberFunction>[] = [
    {
      key: "name",
      header: t("columns.function"),
      sortValue: (row) => row.function_name,
      cell: (row) => (
        <span className="flex items-center gap-2">
          <span className="font-medium">{row.function_name}</span>
          {row.valid_to === null && (
            <Badge variant="secondary">{t("current")}</Badge>
          )}
        </span>
      ),
    },
    {
      key: "division",
      header: t("columns.division"),
      sortValue: (row) => row.division_name,
      cellClassName: "text-muted-foreground",
      cell: (row) => row.division_name ?? "—",
    },
    {
      key: "from",
      header: t("columns.from"),
      shrink: true,
      sortValue: (row) => row.valid_from,
      // Dates only, so the club's zone would change nothing here.
      cell: (row) => formatDate(row.valid_from, locale, "UTC"),
    },
    {
      key: "to",
      header: t("columns.to"),
      shrink: true,
      sortValue: (row) => row.valid_to,
      cellClassName: "text-muted-foreground",
      cell: (row) =>
        row.valid_to ? formatDate(row.valid_to, locale, "UTC") : t("openEnded"),
    },
  ]

  return (
    <DataTable
      data={functions}
      columns={columns}
      rowKey={(row) => row.id}
      defaultSort={{ key: "from", direction: "desc" }}
      emptyText={t("empty")}
      locale={locale}
    />
  )
}
