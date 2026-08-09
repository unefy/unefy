"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { toast } from "sonner"

import { payDueAction } from "@/actions/dues"
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { MyDue } from "@/lib/types/due"
import { CheckIcon } from "lucide-react"

/** How the money arrived. Free text in the API; these are the usual three. */
const METHODS = ["sepa", "transfer", "cash"] as const

export function PayDueDialog({ due }: { due: MyDue }) {
  const t = useTranslations("dues.pay")
  const td = useTranslations("dues")
  const locale = useLocale()
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [method, setMethod] = useState<string>("transfer")
  const [pending, startTransition] = useTransition()

  function submit(formData: FormData) {
    startTransition(async () => {
      const result = await payDueAction(due.id, undefined, formData)
      if (result.success) {
        setOpen(false)
        toast.success(t("paidToast"))
        router.refresh()
      } else {
        toast.error(td(`errors.${result.error}`))
      }
    })
  }

  const amount = Number(due.amount).toLocaleString(locale, {
    style: "currency",
    currency: "EUR",
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button
            variant="ghost"
            size="sm"
            aria-label={t("action")}
            title={t("action")}
          >
            <CheckIcon className="text-primary" />
          </Button>
        }
      />
      <DialogContent>
        <form action={submit}>
          <DialogHeader>
            <DialogTitle>{t("title")}</DialogTitle>
            <DialogDescription>
              {t("description", {
                member: due.member_name ?? "—",
                fee: due.fee_name,
                amount,
              })}
            </DialogDescription>
          </DialogHeader>

          <DialogBody className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="paid_at">{t("fields.paidAt")}</Label>
              {/* Empty means today — the backend fills it in. */}
              <Input id="paid_at" name="paid_at" type="date" />
              <p className="text-xs text-muted-foreground">
                {t("hints.paidAt")}
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="payment_method">{t("fields.method")}</Label>
              <Select
                value={method}
                onValueChange={(value) => setMethod(String(value))}
              >
                <SelectTrigger id="payment_method" className="w-full">
                  <SelectValue>
                    {(value: string) => t(`methods.${value || "transfer"}`)}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {METHODS.map((key) => (
                    <SelectItem key={key} value={key}>
                      {t(`methods.${key}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <input type="hidden" name="payment_method" value={method} />
            </div>

            <div className="space-y-2">
              <Label htmlFor="note">{t("fields.note")}</Label>
              <Input id="note" name="note" maxLength={5000} />
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
            <Button type="submit" disabled={pending}>
              {pending ? t("saving") : t("confirm")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
