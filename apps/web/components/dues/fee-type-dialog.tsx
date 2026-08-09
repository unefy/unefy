"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { createFeeTypeAction, updateFeeTypeAction } from "@/actions/dues"
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
import { Textarea } from "@/components/ui/textarea"
import { FEE_INTERVAL_KEYS, type FeeType } from "@/lib/types/due"
import { PencilIcon, PlusIcon } from "lucide-react"

export function FeeTypeDialog({ feeType }: { feeType?: FeeType }) {
  const t = useTranslations("dues.feeTypes.form")
  const tf = useTranslations("dues.feeTypes")
  const td = useTranslations("dues")
  const router = useRouter()
  const isEdit = feeType !== undefined

  const [open, setOpen] = useState(false)
  const [interval, setInterval] = useState(feeType?.interval ?? "yearly")
  const [pending, startTransition] = useTransition()

  const action = isEdit
    ? updateFeeTypeAction.bind(null, feeType.id)
    : createFeeTypeAction

  function submit(formData: FormData) {
    startTransition(async () => {
      const result = await action(undefined, formData)
      if (result.success) {
        setOpen(false)
        toast.success(isEdit ? t("savedToast") : t("createdToast"))
        router.refresh()
      } else {
        toast.error(td(`errors.${result.error}`))
      }
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          isEdit ? (
            <Button variant="ghost" size="sm" aria-label={t("edit")}>
              <PencilIcon />
            </Button>
          ) : (
            <Button>
              <PlusIcon />
              {t("create")}
            </Button>
          )
        }
      />
      <DialogContent>
        <form action={submit}>
          <DialogHeader>
            <DialogTitle>
              {isEdit ? t("editTitle") : t("createTitle")}
            </DialogTitle>
            <DialogDescription>{t("description")}</DialogDescription>
          </DialogHeader>

          <DialogBody className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">{t("fields.name")}</Label>
              <Input
                id="name"
                name="name"
                required
                maxLength={255}
                defaultValue={feeType?.name ?? ""}
                placeholder={t("placeholders.name")}
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="amount">{t("fields.amount")}</Label>
                <Input
                  id="amount"
                  name="amount"
                  required
                  inputMode="decimal"
                  defaultValue={feeType?.amount ?? ""}
                  placeholder="60,00"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="interval">{t("fields.interval")}</Label>
                <Select
                  value={interval}
                  onValueChange={(value) => setInterval(String(value))}
                >
                  <SelectTrigger id="interval" className="w-full">
                    <SelectValue>
                      {(value: string) =>
                        tf(`intervals.${value || "yearly"}`)
                      }
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {FEE_INTERVAL_KEYS.map((key) => (
                      <SelectItem key={key} value={key}>
                        {tf(`intervals.${key}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <input type="hidden" name="interval" value={interval} />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">{t("fields.description")}</Label>
              <Textarea
                id="description"
                name="description"
                rows={2}
                maxLength={5000}
                defaultValue={feeType?.description ?? ""}
              />
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
              {pending ? t("saving") : t("save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
