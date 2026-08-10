"use client"

import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import {
  DataTable,
  type DataTableColumn,
  type DataTableFilter,
} from "@/components/ui/data-table"
import { formatDate } from "@/lib/time"
import type { MemberAttendanceRecord } from "@/lib/types/attendance"
import type { ShootingRecordDetail } from "@/lib/types/shooting"

/** The words the range book uses, so every screen agrees. */
const WEAPON_KEYS = ["kurzwaffe", "langwaffe", "luftdruck"] as const

/**
 * A member's own range days, club evenings and self-kept ones together.
 *
 * The origin is a column rather than a footnote: what the club attested and
 * what rests on the member's own word count the same towards §14 but are not
 * the same evidence, and the person keeping the record should see which is
 * which.
 */
export function OwnAttendanceTable({
  records,
  details,
  disciplineNames,
  timeZone,
  showShooting,
}: {
  records: MemberAttendanceRecord[]
  /** Keyed by attendance record id; empty for a club without the module. */
  details: Record<string, ShootingRecordDetail>
  /** Club discipline id → name, for the rows that carry one. */
  disciplineNames: Record<string, string>
  timeZone: string
  showShooting: boolean
}) {
  const t = useTranslations("my.attendance")
  const locale = useLocale()

  const columns: DataTableColumn<MemberAttendanceRecord>[] = [
    {
      key: "date",
      header: t("columns.date"),
      shrink: true,
      sortValue: (row) => row.occurred_on,
      cell: (row) => formatDate(row.occurred_on, locale, timeZone),
    },
    {
      key: "where",
      header: t("columns.where"),
      sortValue: (row) => row.session_title ?? row.external_location,
      cell: (row) => (
        <span className="font-medium">
          {row.session_title ?? row.external_location ?? t("ownRange")}
        </span>
      ),
    },
    {
      key: "origin",
      header: t("columns.origin"),
      shrink: true,
      sortValue: (row) => row.origin,
      cell: (row) =>
        row.origin === "external" ? (
          <Badge variant="outline">{t("origin.self")}</Badge>
        ) : (
          <Badge variant="secondary">{t("origin.club")}</Badge>
        ),
    },
  ]

  // Only for a club whose sports carry the module — everyone else has no range
  // book and would get three empty columns.
  if (showShooting) {
    columns.push(
      {
        key: "discipline",
        header: t("columns.discipline"),
        sortValue: (row) => {
          const id = details[row.id]?.club_discipline_id
          return id ? disciplineNames[id] : null
        },
        cellClassName: "text-muted-foreground",
        cell: (row) => {
          const id = details[row.id]?.club_discipline_id
          return (id && disciplineNames[id]) || "—"
        },
      },
      {
        key: "weapon",
        header: t("columns.weapon"),
        shrink: true,
        sortValue: (row) => details[row.id]?.weapon_category,
        cellClassName: "text-muted-foreground",
        cell: (row) => {
          const weapon = details[row.id]?.weapon_category
          return weapon && (WEAPON_KEYS as readonly string[]).includes(weapon)
            ? t(`weapon.${weapon}`)
            : (weapon ?? "—")
        },
      },
      {
        key: "rounds",
        header: t("columns.rounds"),
        align: "right",
        shrink: true,
        sortValue: (row) => details[row.id]?.rounds_fired ?? null,
        cellClassName: "tabular-nums text-muted-foreground",
        cell: (row) => details[row.id]?.rounds_fired ?? "—",
      }
    )
  }

  const filters: DataTableFilter<MemberAttendanceRecord>[] = [
    {
      key: "origin",
      allLabel: t("filters.allOrigins"),
      options: [
        { value: "club", label: t("origin.club") },
        { value: "external", label: t("origin.self") },
      ],
      matches: (row, value) => row.origin === value,
    },
    {
      key: "year",
      allLabel: t("filters.allYears"),
      width: "w-32",
      options: [...new Set(records.map((r) => r.occurred_on.slice(0, 4)))]
        .sort((a, b) => b.localeCompare(a))
        .map((year) => ({ value: year, label: year })),
      matches: (row, value) => row.occurred_on.startsWith(value),
    },
  ]

  return (
    <DataTable
      data={records}
      columns={columns}
      rowKey={(row) => row.id}
      searchPlaceholder={t("searchPlaceholder")}
      searchFields={(row) => [row.session_title, row.external_location]}
      filters={filters}
      defaultSort={{ key: "date", direction: "desc" }}
      emptyText={t("empty")}
      locale={locale}
    />
  )
}
