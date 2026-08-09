"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { toast } from "sonner"

import { createAssignmentAction, deleteAssignmentAction } from "@/actions/dues"
import { euro } from "@/components/dues/dues-table"
import { Button } from "@/components/ui/button"
import { ConfirmAction } from "@/components/ui/confirm-action"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { formatDate } from "@/lib/time"
import type { FeeType, MemberFeeAssignment } from "@/lib/types/due"
import { PlusIcon, Trash2Icon } from "lucide-react"

/**
 * Which fees this member owes, and from when.
 *
 * The assignment is what the yearly assessment reads — a member without one
 * simply produces no dues, which is why this sits on the member rather than in
 * a central list.
 */
export function AssignmentsPanel({
  memberId,
  assignments,
  feeTypes,
  canManage,
}: {
  memberId: string
  assignments: MemberFeeAssignment[]
  feeTypes: FeeType[]
  canManage: boolean
}) {
  const t = useTranslations("dues.assignments")
  const td = useTranslations("dues")
  const locale = useLocale()
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [feeTypeId, setFeeTypeId] = useState(feeTypes[0]?.id ?? "")
  const [pending, startTransition] = useTransition()

  const feeById = new Map(feeTypes.map((fee) => [fee.id, fee]))

  function submit(formData: FormData) {
    startTransition(async () => {
      const result = await createAssignmentAction(memberId, undefined, formData)
      if (result.success) {
        setOpen(false)
        toast.success(t("addedToast"))
        router.refresh()
      } else {
        toast.error(td(`errors.${result.error}`))
      }
    })
  }

  const columns: DataTableColumn<MemberFeeAssignment>[] = [
    {
      key: "fee",
      header: t("columns.fee"),
      sortValue: (row) => feeById.get(row.fee_type_id)?.name,
      cell: (row) => (
        <span className="font-medium">
          {feeById.get(row.fee_type_id)?.name ?? "—"}
        </span>
      ),
    },
    {
      key: "amount",
      header: t("columns.amount"),
      align: "right",
      shrink: true,
      sortValue: (row) => Number(feeById.get(row.fee_type_id)?.amount ?? 0),
      cellClassName: "tabular-nums",
      cell: (row) => {
        const fee = feeById.get(row.fee_type_id)
        return fee ? euro(fee.amount, locale) : "—"
      },
    },
    {
      key: "validFrom",
      header: t("columns.validFrom"),
      shrink: true,
      sortValue: (row) => row.valid_from,
      cell: (row) => formatDate(row.valid_from, locale, "UTC"),
    },
    {
      key: "validTo",
      header: t("columns.validTo"),
      shrink: true,
      sortValue: (row) => row.valid_to,
      cellClassName: "text-muted-foreground",
      cell: (row) =>
        row.valid_to ? formatDate(row.valid_to, locale, "UTC") : t("openEnded"),
    },
    {
      key: "note",
      header: t("columns.note"),
      wrap: true,
      sortValue: (row) => row.note,
      cellClassName: "text-muted-foreground",
      cell: (row) => row.note ?? "—",
    },
  ]

  if (canManage) {
    columns.push({
      key: "actions",
      header: "",
      align: "right",
      shrink: true,
      cell: (row) => (
        <ConfirmAction
          trigger={
            <Button variant="ghost" size="sm" aria-label={t("remove")}>
              <Trash2Icon className="text-destructive" />
            </Button>
          }
          title={t("deleteDialog.title")}
          description={t("deleteDialog.description")}
          confirmLabel={t("deleteDialog.confirm")}
          successMessage={t("removedToast")}
          action={deleteAssignmentAction.bind(null, memberId, row.id)}
        />
      ),
    })
  }

  return (
    <div className="space-y-3">
      {canManage && (
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger
            render={
              <Button variant="outline" size="sm" disabled={feeTypes.length === 0}>
                <PlusIcon />
                {t("add")}
              </Button>
            }
          />
          <DialogContent>
            <form action={submit}>
              <DialogHeader>
                <DialogTitle>{t("addTitle")}</DialogTitle>
                <DialogDescription>{t("addDescription")}</DialogDescription>
              </DialogHeader>

              <DialogBody className="space-y-4">
                <input type="hidden" name="member_id" value={memberId} />
                <div className="space-y-2">
                  <Label htmlFor="fee_type_id">{t("columns.fee")}</Label>
                  <Select
                    value={feeTypeId}
                    onValueChange={(value) => setFeeTypeId(String(value))}
                  >
                    <SelectTrigger id="fee_type_id" className="w-full">
                      <SelectValue>
                        {(value: string) =>
                          feeById.get(value)?.name ?? t("choose")
                        }
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      {feeTypes.map((fee) => (
                        <SelectItem key={fee.id} value={fee.id}>
                          {fee.name} · {euro(fee.amount, locale)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <input type="hidden" name="fee_type_id" value={feeTypeId} />
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="valid_from">{t("columns.validFrom")}</Label>
                    <Input
                      id="valid_from"
                      name="valid_from"
                      type="date"
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="valid_to">{t("columns.validTo")}</Label>
                    <Input id="valid_to" name="valid_to" type="date" />
                    <p className="text-xs text-muted-foreground">
                      {t("validToHint")}
                    </p>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="assignment_note">{t("columns.note")}</Label>
                  <Input id="assignment_note" name="note" maxLength={5000} />
                </div>
              </DialogBody>

              <DialogFooter>
                <DialogClose
                  render={
                    <Button type="button" variant="outline">
                      {t("cancel")}
                    </Button>
                  }
                />
                <Button type="submit" disabled={pending || !feeTypeId}>
                  {pending ? t("saving") : t("save")}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      )}

      <DataTable
        data={assignments}
        columns={columns}
        rowKey={(row) => row.id}
        defaultSort={{ key: "validFrom", direction: "desc" }}
        emptyText={t("empty")}
        locale={locale}
      />
    </div>
  )
}
