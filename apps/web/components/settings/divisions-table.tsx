"use client"

import { useLocale, useTranslations } from "next-intl"

import { deleteDivisionAction } from "@/actions/divisions"
import { DivisionDialog } from "@/components/settings/division-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ConfirmAction } from "@/components/ui/confirm-action"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import type { ClubSport } from "@/lib/types/club"
import type { ClubDivision } from "@/lib/types/functions"
import { Trash2Icon } from "lucide-react"

/**
 * The club's divisions (Sparten).
 *
 * The primary one carries no delete action at all rather than one that fails:
 * every club has exactly one, and offering a button that always refuses is
 * worse than not offering it.
 */
export function DivisionsTable({
  divisions,
  sports,
  canEdit,
}: {
  divisions: ClubDivision[]
  sports: ClubSport[]
  canEdit: boolean
}) {
  const t = useTranslations("clubSettings.divisions")
  const locale = useLocale()

  const sportNames = Object.fromEntries(
    sports.map((sport) => [sport.id, sport.name])
  )

  const columns: DataTableColumn<ClubDivision>[] = [
    {
      key: "name",
      header: t("columns.name"),
      sortValue: (row) => row.name,
      cell: (row) => (
        <span className="flex items-center gap-2">
          <span className="font-medium">{row.name}</span>
          {row.is_primary && (
            <Badge variant="secondary">{t("primary")}</Badge>
          )}
        </span>
      ),
    },
    {
      key: "sport",
      header: t("columns.sport"),
      sortValue: (row) => (row.sport_id ? sportNames[row.sport_id] : null),
      cellClassName: "text-muted-foreground",
      cell: (row) =>
        (row.sport_id && sportNames[row.sport_id]) || t("noSport"),
    },
  ]

  if (canEdit) {
    columns.push({
      key: "actions",
      header: "",
      align: "right",
      shrink: true,
      cell: (row) => (
        <span className="flex items-center justify-end gap-1">
          <DivisionDialog division={row} sports={sports} />
          {!row.is_primary && (
            <ConfirmAction
              trigger={
                <Button variant="ghost" size="sm" aria-label={t("delete")}>
                  <Trash2Icon className="text-destructive" />
                </Button>
              }
              title={t("deleteDialog.title", { name: row.name })}
              description={t("deleteDialog.description")}
              confirmLabel={t("deleteDialog.confirm")}
              successMessage={t("deletedToast")}
              action={deleteDivisionAction.bind(null, row.id)}
            />
          )}
        </span>
      ),
    })
  }

  return (
    <DataTable
      data={divisions}
      columns={columns}
      rowKey={(row) => row.id}
      defaultSort={{ key: "name", direction: "asc" }}
      emptyText={t("empty")}
      locale={locale}
    />
  )
}
