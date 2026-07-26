"use client"

import { useMemo } from "react"
import { useRouter } from "next/navigation"
import { useTranslations, useLocale } from "next-intl"
import type { ColumnDef } from "@tanstack/react-table"
import { Badge } from "@/components/ui/badge"
import { DataTable } from "@/components/common/data-table"
import { useCompetitions } from "@/hooks/use-competitions"
import { formatDate } from "@/lib/date"
import type { Competition } from "@/lib/types/competition"

export function CompetitionsTable() {
  const t = useTranslations("competitions")
  const tc = useTranslations("common")
  const locale = useLocale()
  const router = useRouter()

  const { data, isLoading, error } = useCompetitions()

  const columns = useMemo<ColumnDef<Competition>[]>(
    () => [
      {
        accessorKey: "name",
        size: 220,
        header: t("name"),
        enableSorting: false,
        cell: ({ row }) => (
          <span className="font-medium">{row.original.name}</span>
        ),
      },
      {
        accessorKey: "competition_type",
        size: 130,
        header: t("type"),
        enableSorting: false,
        cell: ({ getValue }) => (
          <Badge variant="secondary">{t(`type_${getValue<string>()}`)}</Badge>
        ),
      },
      {
        accessorKey: "start_date",
        size: 180,
        header: t("period"),
        enableSorting: false,
        cell: ({ row }) => {
          const c = row.original
          return (
            <span>
              {formatDate(c.start_date, locale)}
              {c.end_date ? ` – ${formatDate(c.end_date, locale)}` : ""}
            </span>
          )
        },
      },
      {
        accessorKey: "scoring_unit",
        size: 120,
        header: t("scoringUnit"),
        enableSorting: false,
        cell: ({ getValue }) => (
          <span className="text-muted-foreground">{getValue<string>()}</span>
        ),
        meta: {
          headerClassName: "hidden md:table-cell",
          cellClassName: "hidden md:table-cell",
        },
      },
      {
        accessorKey: "disciplines",
        size: 200,
        header: t("disciplines"),
        enableSorting: false,
        cell: ({ getValue }) => {
          const disciplines = getValue<string[] | null>()
          if (!disciplines || disciplines.length === 0) {
            return <span className="text-muted-foreground">—</span>
          }
          return (
            <span className="text-muted-foreground">
              {disciplines.join(", ")}
            </span>
          )
        },
        meta: {
          headerClassName: "hidden lg:table-cell",
          cellClassName: "hidden lg:table-cell",
        },
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [locale],
  )

  return (
    <DataTable<Competition>
      columns={columns}
      data={data?.data || []}
      isLoading={isLoading}
      error={error ?? null}
      errorStateText={tc("error")}
      getRowId={(row) => row.id}
      onRowClick={(row) => router.push(`/competitions/${row.id}`)}
      emptyState={
        <div className="flex flex-col items-center justify-center py-10 text-center">
          <p className="text-lg font-medium">{t("noCompetitions")}</p>
          <p className="text-muted-foreground mt-1 text-sm">
            {t("noCompetitionsDescription")}
          </p>
        </div>
      }
    />
  )
}
