"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import type { ActionResult } from "@/actions/auth"
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
import { Trash2Icon } from "lucide-react"

/**
 * Confirmation for a destructive master-data change.
 *
 * The server's rejection message is shown verbatim on failure: the backend
 * refuses deletions that would strand data (e.g. a sport that still has
 * disciplines), and that reason is more useful than a generic error.
 */
export function ConfirmDelete({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action: () => Promise<ActionResult>
}) {
  const t = useTranslations("admin.common")
  const tt = useTranslations("admin.toasts")
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="ghost" size="sm" aria-label={t("delete")}>
            <Trash2Icon className="text-destructive" />
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        {error && <p className="py-2 text-sm text-destructive">{error}</p>}

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
            disabled={pending}
            onClick={() =>
              startTransition(async () => {
                const result = await action()
                if (result.success) {
                  setOpen(false)
                  setError(null)
                  toast.success(tt("deleted"))
                  router.refresh()
                } else {
                  // Kept inline rather than shown as a toast: the backend
                  // explains *why* it refused, and that reason has to stay
                  // readable next to the button instead of fading away.
                  setError(result.error)
                }
              })
            }
          >
            {pending ? t("deleting") : t("delete")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
