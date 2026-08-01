"use client"

import { useState, useTransition, type ReactElement } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import type { ActionResult } from "@/actions/attendance"
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

/** Mirrors the backend rule: a reason shorter than this is not a reason. */
const MIN_REASON = 3

/**
 * Confirmation that insists on a written reason.
 *
 * Removing an attendance record is not a delete — it is a correction to a
 * record of evidence, and the reason is what the audit trail is for. So the
 * reason is the gate, not a nicety: the confirm button stays disabled without
 * one.
 */
export function ReasonDialog({
  trigger,
  title,
  description,
  confirmLabel,
  successMessage,
  action,
}: {
  trigger: ReactElement
  title: string
  description: string
  confirmLabel: string
  successMessage: string
  action: (reason: string) => Promise<ActionResult>
}) {
  const t = useTranslations("attendance.form")
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState("")
  const [pending, startTransition] = useTransition()

  const valid = reason.trim().length >= MIN_REASON

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) setReason("")
      }}
    >
      <DialogTrigger render={trigger} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-2">
          <Label htmlFor="reason">{t("fields.reason")}</Label>
          <Textarea
            id="reason"
            value={reason}
            maxLength={1000}
            rows={3}
            onChange={(event) => setReason(event.target.value)}
            placeholder={t("placeholders.reason")}
          />
          <p className="text-xs text-muted-foreground">{t("hints.reason")}</p>
        </DialogBody>

        <DialogFooter>
          <DialogClose
            render={
              <Button type="button" variant="outline">
                {t("cancel")}
              </Button>
            }
          />
          <Button
            variant="destructive"
            disabled={pending || !valid}
            onClick={() =>
              startTransition(async () => {
                const result = await action(reason.trim())
                if (result.success) {
                  setOpen(false)
                  setReason("")
                  toast.success(successMessage)
                  router.refresh()
                } else {
                  toast.error(t(`errors.${result.error}`))
                }
              })
            }
          >
            {pending ? t("saving") : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
