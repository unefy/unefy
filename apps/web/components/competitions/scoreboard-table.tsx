"use client"

import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import {
  DataTable,
  type DataTableColumn,
  type DataTableFilter,
} from "@/components/ui/data-table"
import type { Scoreboard, ScoreboardRow } from "@/lib/types/competition"

/**
 * Formats a result without inventing precision.
 *
 * A time of 12.34 s and 60 points both arrive as plain numbers; showing
 * "60,00" for a ring count reads wrong, so trailing zeroes are dropped.
 */
export function formatScore(value: number, locale: string): string {
  return value.toLocaleString(locale, { maximumFractionDigits: 3 })
}

export function ScoreboardTable({
  scoreboard,
  disciplines,
}: {
  scoreboard: Scoreboard
  /** The competition's disciplines, for the filter. */
  disciplines: string[]
}) {
  const t = useTranslations("competitions.scoreboard")
  const locale = useLocale()

  const unit = scoreboard.scoring_unit

  const columns: DataTableColumn<ScoreboardRow>[] = [
    {
      key: "rank",
      header: t("columns.rank"),
      align: "right",
      shrink: true,
      sortValue: (row) => row.rank,
      cellClassName: "tabular-nums",
      cell: (row) =>
        row.rank <= 3 ? (
          <Badge variant={row.rank === 1 ? "default" : "secondary"}>
            {row.rank}
          </Badge>
        ) : (
          <span className="text-muted-foreground">{row.rank}</span>
        ),
    },
    {
      key: "member",
      header: t("columns.member"),
      sortValue: (row) => row.member_name,
      cell: (row) => <span className="font-medium">{row.member_name}</span>,
    },
    {
      key: "total",
      header: `${t("columns.total")} (${unit})`,
      align: "right",
      shrink: true,
      sortValue: (row) => row.total_score,
      cellClassName: "tabular-nums font-medium",
      cell: (row) => formatScore(row.total_score, locale),
    },
    {
      key: "best",
      header: t("columns.best"),
      align: "right",
      shrink: true,
      sortValue: (row) => row.best_score,
      cellClassName: "tabular-nums text-muted-foreground",
      cell: (row) => formatScore(row.best_score, locale),
    },
    {
      key: "average",
      header: t("columns.average"),
      align: "right",
      shrink: true,
      sortValue: (row) => row.average_score,
      cellClassName: "tabular-nums text-muted-foreground",
      cell: (row) => formatScore(row.average_score, locale),
    },
    {
      key: "entries",
      header: t("columns.entries"),
      align: "right",
      shrink: true,
      sortValue: (row) => row.entry_count,
      cellClassName: "tabular-nums text-muted-foreground",
      cell: (row) => String(row.entry_count),
    },
  ]

  const filters: DataTableFilter<ScoreboardRow>[] = []

  return (
    <div className="space-y-2">
      <DataTable
        data={scoreboard.rows}
        columns={columns}
        rowKey={(row) => row.member_id}
        searchPlaceholder={t("searchPlaceholder")}
        searchFields={(row) => [row.member_name]}
        filters={filters}
        // Already ranked by the backend, which is the only place that knows
        // whether high or low wins. Sorting by rank preserves that.
        defaultSort={{ key: "rank", direction: "asc" }}
        emptyText={t("empty")}
        locale={locale}
      />
      {disciplines.length > 0 && (
        <p className="text-xs text-muted-foreground">
          {t("disciplineHint", { disciplines: disciplines.join(", ") })}
        </p>
      )}
    </div>
  )
}
