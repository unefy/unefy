"use client"

import { useTransition } from "react"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { toast } from "sonner"

import { deleteFeeTypeAction, setFeeTypeActiveAction } from "@/actions/dues"
import { FeeTypeDialog } from "@/components/dues/fee-type-dialog"
import { euro } from "@/components/dues/dues-table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ConfirmAction } from "@/components/ui/confirm-action"
import {
  DataTable,
  type DataTableColumn,
  type DataTableFilter,
} from "@/components/ui/data-table"
import type { FeeType } from "@/lib/types/due"
import { ArchiveIcon, ArchiveRestoreIcon, Trash2Icon } from "lucide-react"

/**
 * The club's fee catalogue.
 *
 * Retiring is offered before deleting: a fee type that has already produced
 * dues should stop being assigned, not disappear from the books.
 */
export function FeeTypesTable({
  feeTypes,
  canEdit,
  canDelete,
}: {
  feeTypes: FeeType[]
  canEdit: boolean
  /** Deleting is owner/admin in the backend. */
  canDelete: boolean
}) {
  const t = useTranslations("dues.feeTypes")
  const td = useTranslations("dues")
  const locale = useLocale()
  const router = useRouter()
  const [pending, startTransition] = useTransition()

  function toggleActive(feeType: FeeType) {
    startTransition(async () => {
      const result = await setFeeTypeActiveAction(
        feeType.id,
        !feeType.is_active
      )
      if (result.success) {
        toast.success(feeType.is_active ? t("retiredToast") : t("revivedToast"))
        router.refresh()
      } else {
        toast.error(td(`errors.${result.error}`))
      }
    })
  }

  const columns: DataTableColumn<FeeType>[] = [
    {
      key: "name",
      header: t("columns.name"),
      sortValue: (row) => row.name,
      cell: (row) => <span className="font-medium">{row.name}</span>,
    },
    {
      key: "amount",
      header: t("columns.amount"),
      align: "right",
      shrink: true,
      sortValue: (row) => Number(row.amount),
      cellClassName: "tabular-nums",
      cell: (row) => euro(row.amount, locale),
    },
    {
      key: "interval",
      header: t("columns.interval"),
      shrink: true,
      sortValue: (row) => row.interval,
      cell: (row) => t(`intervals.${row.interval}`),
    },
    {
      key: "description",
      header: t("columns.description"),
      wrap: true,
      sortValue: (row) => row.description,
      cellClassName: "text-muted-foreground",
      cell: (row) => row.description ?? "—",
    },
    {
      key: "status",
      header: t("columns.status"),
      shrink: true,
      sortValue: (row) => row.is_active,
      cell: (row) => (
        <Badge variant={row.is_active ? "secondary" : "outline"}>
          {row.is_active ? t("active") : t("retired")}
        </Badge>
      ),
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
          <FeeTypeDialog feeType={row} />
          <Button
            variant="ghost"
            size="sm"
            disabled={pending}
            aria-label={row.is_active ? t("retire") : t("revive")}
            title={row.is_active ? t("retire") : t("revive")}
            onClick={() => toggleActive(row)}
          >
            {row.is_active ? (
              <ArchiveIcon className="text-muted-foreground" />
            ) : (
              <ArchiveRestoreIcon className="text-muted-foreground" />
            )}
          </Button>
          {canDelete && (
            <ConfirmAction
              trigger={
                <Button variant="ghost" size="sm" aria-label={t("delete")}>
                  <Trash2Icon className="text-destructive" />
                </Button>
              }
              title={t("deleteDialog.title")}
              description={t("deleteDialog.description")}
              confirmLabel={t("deleteDialog.confirm")}
              successMessage={t("deletedToast")}
              action={deleteFeeTypeAction.bind(null, row.id)}
            />
          )}
        </span>
      ),
    })
  }

  const filters: DataTableFilter<FeeType>[] = [
    {
      key: "status",
      allLabel: t("filters.allStatuses"),
      options: [
        { value: "active", label: t("active") },
        { value: "retired", label: t("retired") },
      ],
      matches: (row, value) =>
        value === "active" ? row.is_active : !row.is_active,
    },
  ]

  return (
    <DataTable
      data={feeTypes}
      columns={columns}
      rowKey={(row) => row.id}
      searchPlaceholder={t("searchPlaceholder")}
      searchFields={(row) => [row.name, row.description]}
      filters={filters}
      defaultSort={{ key: "name", direction: "asc" }}
      emptyText={t("empty")}
      locale={locale}
    />
  )
}
