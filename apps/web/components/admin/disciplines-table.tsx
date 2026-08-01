"use client"

import { useMemo, type ReactNode } from "react"
import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import type { CatalogDiscipline, Sport } from "@/lib/types/admin"

export function DisciplinesTable({
  disciplines,
  sports,
  actions,
}: {
  disciplines: CatalogDiscipline[]
  sports: Sport[]
  /** Row actions rendered on the server, keyed by discipline id. */
  actions: Record<string, ReactNode>
}) {
  const t = useTranslations("admin.disciplines")
  const locale = useLocale()

  const sportName = useMemo(
    () => new Map(sports.map((sport) => [sport.id, sport.name])),
    [sports]
  )
  const nameOf = (row: CatalogDiscipline) =>
    row.sport_id ? (sportName.get(row.sport_id) ?? null) : null

  const federations = useMemo(
    () => [...new Set(disciplines.map((d) => d.federation))].sort(),
    [disciplines]
  )

  const columns: DataTableColumn<CatalogDiscipline>[] = [
    {
      key: "name",
      header: t("columns.name"),
      sortValue: (row) => row.name,
      cell: (row) => (
        <>
          <div className="font-medium">{row.name}</div>
          <div className="font-mono text-xs text-muted-foreground">
            {row.slug}
          </div>
        </>
      ),
    },
    {
      key: "sport",
      header: t("columns.sport"),
      sortValue: (row) => nameOf(row),
      cellClassName: "text-muted-foreground",
      cell: (row) => nameOf(row) ?? "—",
    },
    {
      key: "federation",
      header: t("columns.federation"),
      sortValue: (row) => row.federation,
      cell: (row) => <Badge variant="outline">{row.federation}</Badge>,
    },
    {
      key: "category",
      header: t("columns.category"),
      sortValue: (row) => row.category,
      cellClassName: "text-muted-foreground",
      cell: (row) => row.category,
    },
    {
      key: "scoring",
      header: t("columns.scoring"),
      sortValue: (row) => row.scoring_unit,
      cellClassName: "text-muted-foreground",
      cell: (row) => (
        <>
          {row.scoring_unit}
          <span className="ms-1 text-xs">
            ({t(`dialog.modes.${row.scoring_mode}`)})
          </span>
        </>
      ),
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
      data={disciplines}
      columns={columns}
      rowKey={(row) => row.id}
      locale={locale}
      defaultSort={{ key: "name", direction: "asc" }}
      searchPlaceholder={t("searchPlaceholder")}
      searchFields={(row) => [row.name, row.slug, row.federation, row.category]}
      filters={[
        {
          key: "sport",
          allLabel: t("filters.allSports"),
          width: "w-52",
          options: sports.map((sport) => ({
            value: sport.id,
            label: sport.name,
          })),
          matches: (row, value) => row.sport_id === value,
        },
        {
          key: "federation",
          allLabel: t("filters.allFederations"),
          options: federations.map((federation) => ({
            value: federation,
            label: federation,
          })),
          matches: (row, value) => row.federation === value,
        },
      ]}
      emptyText={t("empty")}
    />
  )
}
