"use client"

import { useLocale, useTranslations } from "next-intl"

import { deleteFunctionAction } from "@/actions/functions"
import { ConfirmDelete } from "@/components/admin/confirm-delete"
import { FunctionDialog } from "@/components/settings/function-dialog"
import { Badge } from "@/components/ui/badge"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import { roleLabel } from "@/lib/labels"
import type { ClubFunction } from "@/lib/types/functions"

export function FunctionsTable({
  functions,
  hasDivisions,
  canEdit,
}: {
  functions: ClubFunction[]
  hasDivisions: boolean
  canEdit: boolean
}) {
  const t = useTranslations("clubSettings.functions")
  const tr = useTranslations("admin")
  const locale = useLocale()

  const columns: DataTableColumn<ClubFunction>[] = [
    {
      key: "name",
      header: t("columns.name"),
      sortValue: (row) => row.name,
      cell: (row) => (
        <span className={row.is_active ? "font-medium" : "text-muted-foreground"}>
          {row.name}
        </span>
      ),
    },
    ...(hasDivisions
      ? [
          {
            key: "level",
            header: t("columns.level"),
            sortValue: (row) => row.level,
            cellClassName: "text-muted-foreground",
            cell: (row) => t(`levels.${row.level}`),
          } satisfies DataTableColumn<ClubFunction>,
        ]
      : []),
    {
      key: "suggestedRole",
      header: t("columns.suggestedRole"),
      sortValue: (row) => row.suggested_role,
      cellClassName: "text-muted-foreground",
      cell: (row) =>
        row.suggested_role ? roleLabel(tr, row.suggested_role) : "—",
    },
    {
      key: "active",
      header: t("columns.active"),
      shrink: true,
      sortValue: (row) => (row.is_active ? 0 : 1),
      cell: (row) =>
        row.is_active ? (
          <Badge variant="secondary">{t("active")}</Badge>
        ) : (
          <Badge variant="outline">{t("inactive")}</Badge>
        ),
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
    ...(canEdit
      ? [
          {
            key: "actions",
            header: "",
            align: "right",
            shrink: true,
            cell: (row) => (
              <div className="flex justify-end">
                <FunctionDialog func={row} hasDivisions={hasDivisions} />
                <ConfirmDelete
                  title={t("deleteTitle", { name: row.name })}
                  description={t("deleteDescription")}
                  action={async () => {
                    const result = await deleteFunctionAction(row.id)
                    if (!result.success && result.error === "conflict") {
                      return { success: false, error: t("deleteConflict") }
                    }
                    return result
                  }}
                />
              </div>
            ),
          } satisfies DataTableColumn<ClubFunction>,
        ]
      : []),
  ]

  return (
    <DataTable
      data={functions}
      columns={columns}
      rowKey={(row) => row.id}
      locale={locale}
      defaultSort={{ key: "sortOrder", direction: "asc" }}
      emptyText={t("empty")}
    />
  )
}
