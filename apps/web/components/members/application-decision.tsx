"use client"

import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import {
  acceptApplicationAction,
  rejectApplicationAction,
} from "@/actions/applications"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

/**
 * Accept or reject — the two buttons this whole feature exists for.
 *
 * Acceptance goes through a confirmation because it creates a member and a
 * member number, and neither can be taken back by clicking again.
 */
export function ApplicationDecision({
  applicationId,
  applicantName,
}: {
  applicationId: string
  applicantName: string
}) {
  const t = useTranslations("applications")
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [confirming, setConfirming] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [note, setNote] = useState("")

  function accept() {
    startTransition(async () => {
      const result = await acceptApplicationAction(applicationId)
      if (!result.success) {
        toast.error(t(`errors.${result.error}`))
        return
      }
      setConfirming(false)
      toast.success(t("accepted"))
      // Straight to the new member: admitting somebody is the start of their
      // record, not the end of the application.
      router.push(`/members/${result.data?.id}`)
    })
  }

  function reject() {
    startTransition(async () => {
      const result = await rejectApplicationAction(applicationId, note)
      if (!result.success) {
        toast.error(t(`errors.${result.error}`))
        return
      }
      setRejecting(false)
      toast.success(t("rejected"))
      router.refresh()
    })
  }

  return (
    <div className="flex flex-wrap gap-2">
      <Button onClick={() => setConfirming(true)} disabled={pending}>
        {t("accept")}
      </Button>
      <Button
        variant="outline"
        onClick={() => setRejecting(true)}
        disabled={pending}
      >
        {t("reject")}
      </Button>

      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("confirmAccept.title")}</DialogTitle>
            <DialogDescription>
              {t("confirmAccept.description", { name: applicantName })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setConfirming(false)}
              disabled={pending}
            >
              {t("cancel")}
            </Button>
            <Button onClick={accept} disabled={pending}>
              {t("accept")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={rejecting} onOpenChange={setRejecting}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("confirmReject.title")}</DialogTitle>
            <DialogDescription>
              {t("confirmReject.description")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="decision-note">{t("noteLabel")}</Label>
            <Textarea
              id="decision-note"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={3}
              maxLength={2000}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setRejecting(false)}
              disabled={pending}
            >
              {t("cancel")}
            </Button>
            <Button variant="destructive" onClick={reject} disabled={pending}>
              {t("reject")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
