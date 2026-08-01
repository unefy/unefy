"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { closeSessionAction } from "@/actions/attendance"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { LockIcon } from "lucide-react"

/**
 * Closing freezes the session for good — there is no reopen endpoint, and the
 * dialog says so plainly. This is the one irreversible action on the page, and
 * the confirmation exists to make that unmissable rather than to slow anyone
 * down.
 */
export function CloseSessionDialog({
  sessionId,
  recordCount,
}: {
  sessionId: string
  recordCount: number
}) {
  const t = useTranslations("attendance")
  const tf = useTranslations("attendance.form")
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [pending, startTransition] = useTransition()

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="outline" size="sm">
            <LockIcon />
            {t("close")}
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("closeDialog.title")}</DialogTitle>
          <DialogDescription>
            {t("closeDialog.description", { count: recordCount })}
          </DialogDescription>
        </DialogHeader>

        <DialogFooter>
          <DialogClose
            render={
              <Button type="button" variant="outline">
                {tf("cancel")}
              </Button>
            }
          />
          <Button
            disabled={pending}
            onClick={() =>
              startTransition(async () => {
                const result = await closeSessionAction(sessionId)
                if (result.success) {
                  setOpen(false)
                  toast.success(t("toasts.closed"))
                  router.refresh()
                } else {
                  toast.error(tf(`errors.${result.error}`))
                }
              })
            }
          >
            {pending ? tf("saving") : t("closeDialog.confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
