"use client"

import { useState } from "react"
import { useTranslations, useLocale } from "next-intl"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { ConfirmDialog } from "@/components/common/confirm-dialog"
import { FeeTypeDialog } from "@/components/dues/fee-type-dialog"
import { useDeleteFeeType, useFeeTypes } from "@/hooks/use-dues"
import { useErrorMessage } from "@/lib/errors"
import { formatCurrency } from "@/lib/currency"
import { Trash2, Pencil } from "lucide-react"
import type { FeeType } from "@/lib/types/due"

export function FeeTypesTable() {
  const t = useTranslations("dues")
  const tc = useTranslations("common")
  const locale = useLocale()
  const getErrorMessage = useErrorMessage()

  const { data: feeTypes, isLoading } = useFeeTypes(true)
  const deleteFeeType = useDeleteFeeType()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<FeeType | null>(null)
  const [deleting, setDeleting] = useState<FeeType | null>(null)

  function openCreate() {
    setEditing(null)
    setDialogOpen(true)
  }

  function openEdit(feeType: FeeType) {
    setEditing(feeType)
    setDialogOpen(true)
  }

  async function handleDelete() {
    if (!deleting) return
    try {
      await deleteFeeType.mutateAsync(deleting.id)
      toast.success(tc("saved"))
      setDeleting(null)
    } catch (err) {
      toast.error(getErrorMessage(err))
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={openCreate}>{t("addFeeType")}</Button>
      </div>

      {isLoading ? (
        <div className="divide-y rounded-lg border">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex gap-4 p-4">
              <div className="h-4 flex-1 animate-pulse rounded bg-muted" />
              <div className="h-4 w-20 animate-pulse rounded bg-muted" />
              <div className="h-4 w-24 animate-pulse rounded bg-muted" />
            </div>
          ))}
        </div>
      ) : !feeTypes || feeTypes.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border py-10 text-center">
          <p className="text-lg font-medium">{t("noFeeTypes")}</p>
          <p className="text-muted-foreground mt-1 text-sm">
            {t("noFeeTypesDescription")}
          </p>
        </div>
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("feeName")}</TableHead>
                <TableHead>{t("amount")}</TableHead>
                <TableHead>{t("interval")}</TableHead>
                <TableHead>{t("status")}</TableHead>
                <TableHead className="w-20" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {feeTypes.map((feeType) => (
                <TableRow key={feeType.id}>
                  <TableCell>
                    <span className="font-medium">{feeType.name}</span>
                    {feeType.description && (
                      <p className="text-muted-foreground mt-0.5 max-w-md truncate text-xs">
                        {feeType.description}
                      </p>
                    )}
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {formatCurrency(feeType.amount, locale)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {t(`interval_${feeType.interval}`)}
                  </TableCell>
                  <TableCell>
                    <Badge variant={feeType.is_active ? "default" : "secondary"}>
                      {feeType.is_active ? t("active") : t("inactive")}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <button
                        onClick={() => openEdit(feeType)}
                        className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
                        aria-label={tc("edit")}
                      >
                        <Pencil size={15} />
                      </button>
                      <button
                        onClick={() => setDeleting(feeType)}
                        className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
                        aria-label={tc("delete")}
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <FeeTypeDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        feeType={editing}
      />

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={t("deleteFeeType")}
        description={t("deleteFeeTypeConfirm", { name: deleting?.name ?? "" })}
        destructive
        pending={deleteFeeType.isPending}
        onConfirm={handleDelete}
      />
    </div>
  )
}
