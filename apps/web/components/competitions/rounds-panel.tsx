"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { toast } from "sonner"

import {
  createSessionAction,
  deleteSessionAction,
} from "@/actions/competitions"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
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
import { formatDate } from "@/lib/time"
import type { CompetitionSession } from "@/lib/types/competition"
import { CalendarIcon, PlusIcon, Trash2Icon } from "lucide-react"

/**
 * The rounds of a competition — match days, legs, training evenings.
 *
 * A round can also be put in the calendar, which is where registration then
 * happens; the results stay here. That split is the whole reason both layers
 * exist.
 */
export function RoundsPanel({
  competitionId,
  sessions,
  timeZone,
  canManage,
  canDelete,
}: {
  competitionId: string
  sessions: CompetitionSession[]
  timeZone: string
  canManage: boolean
  /** Deleting a round is owner/admin in the backend. */
  canDelete: boolean
}) {
  const t = useTranslations("competitions.rounds")
  const tc = useTranslations("competitions")
  const locale = useLocale()
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [withEvent, setWithEvent] = useState(false)
  const [pending, startTransition] = useTransition()

  function submit(formData: FormData) {
    startTransition(async () => {
      const result = await createSessionAction(
        competitionId,
        withEvent,
        undefined,
        formData
      )
      if (result.success) {
        setOpen(false)
        toast.success(t("addedToast"))
        router.refresh()
      } else {
        toast.error(tc(`errors.${result.error}`))
      }
    })
  }

  const columns: DataTableColumn<CompetitionSession>[] = [
    {
      key: "date",
      header: t("columns.date"),
      shrink: true,
      sortValue: (row) => row.date,
      cell: (row) => formatDate(row.date, locale, timeZone),
    },
    {
      key: "name",
      header: t("columns.name"),
      sortValue: (row) => row.name,
      cell: (row) => (
        <span className="flex items-center gap-2">
          <span className="font-medium">{row.name ?? t("unnamed")}</span>
          {row.event_id && (
            <Badge variant="outline" className="gap-1">
              <CalendarIcon className="size-3" />
              {t("inCalendar")}
            </Badge>
          )}
        </span>
      ),
    },
    {
      key: "location",
      header: t("columns.location"),
      sortValue: (row) => row.location,
      cellClassName: "text-muted-foreground",
      cell: (row) => row.location ?? "—",
    },
    {
      key: "discipline",
      header: t("columns.discipline"),
      shrink: true,
      sortValue: (row) => row.discipline,
      cellClassName: "text-muted-foreground",
      cell: (row) => row.discipline ?? "—",
    },
  ]

  if (canDelete) {
    columns.push({
      key: "actions",
      header: "",
      align: "right",
      shrink: true,
      cell: (row) => (
        <span onClick={(event) => event.stopPropagation()}>
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
            action={deleteSessionAction.bind(null, competitionId, row.id)}
          />
        </span>
      ),
    })
  }

  return (
    <div className="space-y-3">
      {canManage && (
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger
            render={
              <Button variant="outline" size="sm">
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
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="round_date">{t("columns.date")}</Label>
                    <Input id="round_date" name="date" type="date" required />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="round_name">{t("columns.name")}</Label>
                    <Input
                      id="round_name"
                      name="name"
                      maxLength={255}
                      placeholder={t("namePlaceholder")}
                    />
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="round_location">
                      {t("columns.location")}
                    </Label>
                    <Input
                      id="round_location"
                      name="location"
                      maxLength={255}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="round_discipline">
                      {t("columns.discipline")}
                    </Label>
                    <Input
                      id="round_discipline"
                      name="discipline"
                      maxLength={100}
                    />
                  </div>
                </div>

                <label className="flex items-start gap-2 rounded-md border p-3 text-sm">
                  <Checkbox
                    checked={withEvent}
                    onCheckedChange={(checked) => setWithEvent(checked === true)}
                  />
                  <span>
                    {t("withEvent")}
                    <span className="block text-xs text-muted-foreground">
                      {t("withEventHint")}
                    </span>
                  </span>
                </label>
              </DialogBody>

              <DialogFooter>
                <DialogClose
                  render={
                    <Button type="button" variant="outline">
                      {t("cancel")}
                    </Button>
                  }
                />
                <Button type="submit" disabled={pending}>
                  {pending ? t("saving") : t("save")}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      )}

      <DataTable
        data={sessions}
        columns={columns}
        rowKey={(row) => row.id}
        onRowClick={(row) =>
          router.push(`/competitions/${competitionId}/rounds/${row.id}`)
        }
        defaultSort={{ key: "date", direction: "desc" }}
        emptyText={t("empty")}
        locale={locale}
      />
    </div>
  )
}
