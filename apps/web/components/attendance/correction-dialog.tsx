"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { correctRecordAction } from "@/actions/attendance"
import { Button } from "@/components/ui/button"
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
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import type { AttendanceRecord } from "@/lib/types/attendance"
import { PencilIcon } from "lucide-react"

/**
 * Correct a record's note. Every save writes an audit entry, so the reason is
 * a required field rather than an optional afterthought.
 */
export function CorrectionDialog({
  sessionId,
  record,
}: {
  sessionId: string
  record: AttendanceRecord
}) {
  const t = useTranslations("attendance")
  const tf = useTranslations("attendance.form")
  const router = useRouter()
  const [open, setOpen] = useState(false)

  const [pending, startTransition] = useTransition()

  function submit(formData: FormData) {
    startTransition(async () => {
      const result = await correctRecordAction(
        sessionId,
        record.id,
        undefined,
        formData
      )
      if (result.success) {
        setOpen(false)
        toast.success(t("toasts.corrected"))
        router.refresh()
      } else {
        toast.error(tf(`errors.${result.error}`))
      }
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button
            variant="ghost"
            size="sm"
            aria-label={t("correct")}
            title={t("correct")}
          >
            <PencilIcon />
          </Button>
        }
      />
      <DialogContent>
        <form action={submit}>
          <DialogHeader>
            <DialogTitle>
              {t("correctDialog.title", { name: record.member_name ?? "" })}
            </DialogTitle>
            <DialogDescription>
              {t("correctDialog.description")}
            </DialogDescription>
          </DialogHeader>

          <DialogBody className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor={`note-${record.id}`}>{tf("fields.note")}</Label>
              <Textarea
                id={`note-${record.id}`}
                name="note"
                rows={2}
                maxLength={1000}
                defaultValue={record.note ?? ""}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor={`reason-${record.id}`}>
                {tf("fields.reason")}
              </Label>
              <Textarea
                id={`reason-${record.id}`}
                name="reason"
                rows={2}
                required
                minLength={3}
                maxLength={1000}
                placeholder={tf("placeholders.reason")}
              />
              <p className="text-xs text-muted-foreground">
                {tf("hints.reason")}
              </p>
            </div>
          </DialogBody>

          <DialogFooter>
            <DialogClose
              render={
                <Button type="button" variant="outline">
                  {tf("cancel")}
                </Button>
              }
            />
            <Button type="submit" disabled={pending}>
              {pending ? tf("saving") : tf("save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
