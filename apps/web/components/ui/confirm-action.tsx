"use client"

import { useState, useTransition, type ReactElement } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

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

type Result = { success: true } | { success: false; error: string }

/**
 * Confirmation for an action that needs no written reason.
 *
 * The sibling of `ReasonDialog`: attendance corrections change a record of
 * evidence and must say why, whereas cancelling or deleting an event only
 * needs to be meant. Same shape, so both read the same on a page.
 */
export function ConfirmAction({
  trigger,
  title,
  description,
  confirmLabel,
  successMessage,
  action,
  redirectTo,
  variant = "destructive",
}: {
  trigger: ReactElement
  title: string
  description: string
  confirmLabel: string
  successMessage: string
  action: () => Promise<Result>
  /** Where to go afterwards — for actions that remove the current page. */
  redirectTo?: string
  variant?: "destructive" | "default"
}) {
  const t = useTranslations("common.confirm")
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [pending, startTransition] = useTransition()

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={trigger} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <DialogFooter>
          <DialogClose
            render={
              <Button type="button" variant="outline">
                {t("cancel")}
              </Button>
            }
          />
          <Button
            variant={variant}
            disabled={pending}
            onClick={() =>
              startTransition(async () => {
                const result = await action()
                if (result.success) {
                  setOpen(false)
                  toast.success(successMessage)
                  if (redirectTo) router.push(redirectTo)
                  else router.refresh()
                } else {
                  toast.error(t(`errors.${result.error}`))
                }
              })
            }
          >
            {pending ? t("working") : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
