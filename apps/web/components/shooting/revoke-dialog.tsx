"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { revokeCertificateAction } from "@/actions/shooting"
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
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import type { ShootingCertificate } from "@/lib/types/shooting"
import { BanIcon } from "lucide-react"

/** Revoking is a statement about evidence, so it insists on a reason. */
export function RevokeDialog({
  certificate,
}: {
  certificate: ShootingCertificate
}) {
  const t = useTranslations("shooting.revoke")
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState("")
  const [pending, startTransition] = useTransition()

  const submit = () => {
    startTransition(async () => {
      const result = await revokeCertificateAction(certificate.id, reason)
      if (result.success) {
        setOpen(false)
        setReason("")
        toast.success(t("revokedToast"))
        router.refresh()
      } else {
        toast.error(t(`errors.${result.error}`))
      }
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="ghost" size="sm" aria-label={t("action")}>
            <BanIcon className="text-destructive" />
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {t("title", { name: certificate.member_name ?? "" })}
          </DialogTitle>
          <DialogDescription>{t("description")}</DialogDescription>
        </DialogHeader>

        <div className="space-y-2 py-2">
          <Label htmlFor="revoke-reason">{t("reason")}</Label>
          <Textarea
            id="revoke-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder={t("reasonPlaceholder")}
          />
        </div>

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
            disabled={pending || reason.trim().length < 3}
            onClick={submit}
          >
            {pending ? t("revoking") : t("action")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
