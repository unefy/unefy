"use client"

import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import {
  DataTable,
  type DataTableColumn,
  type DataTableFilter,
} from "@/components/ui/data-table"
import { formatDate } from "@/lib/time"
import {
  COMPETITION_TYPE_KEYS,
  type Competition,
} from "@/lib/types/competition"

export function CompetitionsTable({
  competitions,
  timeZone,
}: {
  competitions: Competition[]
  timeZone: string
}) {
  const t = useTranslations("competitions")
  const locale = useLocale()
  const router = useRouter()

  const columns: DataTableColumn<Competition>[] = [
    {
      key: "name",
      header: t("columns.name"),
      sortValue: (row) => row.name,
      cell: (row) => <span className="font-medium">{row.name}</span>,
    },
    {
      key: "type",
      header: t("columns.type"),
      shrink: true,
      sortValue: (row) => t(`types.${row.competition_type}`),
      cell: (row) => (
        <Badge variant="secondary">{t(`types.${row.competition_type}`)}</Badge>
      ),
    },
    {
      key: "start",
      header: t("columns.period"),
      shrink: true,
      sortValue: (row) => row.start_date,
      cellClassName: "text-muted-foreground",
      cell: (row) =>
        row.end_date && row.end_date !== row.start_date
          ? `${formatDate(row.start_date, locale, timeZone)} – ${formatDate(row.end_date, locale, timeZone)}`
          : formatDate(row.start_date, locale, timeZone),
    },
    {
      key: "scoring",
      header: t("columns.scoring"),
      shrink: true,
      sortValue: (row) => row.scoring_unit,
      cellClassName: "text-muted-foreground",
      // The unit and the direction together are what makes a number readable —
      // 12 seconds beats 14, 12 points does not.
      cell: (row) => `${row.scoring_unit} · ${t(`modes.${row.scoring_mode}`)}`,
    },
    {
      key: "disciplines",
      header: t("columns.disciplines"),
      wrap: true,
      sortValue: (row) => row.disciplines?.join(", "),
      cell: (row) =>
        row.disciplines?.length ? (
          <span className="flex flex-wrap gap-1">
            {row.disciplines.map((discipline) => (
              <Badge key={discipline} variant="outline">
                {discipline}
              </Badge>
            ))}
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
  ]

  const filters: DataTableFilter<Competition>[] = [
    {
      key: "type",
      allLabel: t("filters.allTypes"),
      options: COMPETITION_TYPE_KEYS.map((key) => ({
        value: key,
        label: t(`types.${key}`),
      })),
      matches: (row, value) => row.competition_type === value,
    },
  ]

  return (
    <DataTable
      data={competitions}
      columns={columns}
      rowKey={(row) => row.id}
      onRowClick={(row) => router.push(`/competitions/${row.id}`)}
      searchPlaceholder={t("searchPlaceholder")}
      searchFields={(row) => [
        row.name,
        row.description,
        row.disciplines?.join(" "),
      ]}
      filters={filters}
      defaultSort={{ key: "start", direction: "desc" }}
      emptyText={t("empty")}
      locale={locale}
    />
  )
}
