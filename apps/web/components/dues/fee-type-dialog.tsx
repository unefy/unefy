"use client"

import { useEffect, useState } from "react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useCreateFeeType, useUpdateFeeType } from "@/hooks/use-dues"
import { useErrorMessage } from "@/lib/errors"
import type { FeeInterval, FeeType } from "@/lib/types/due"

const INTERVALS: FeeInterval[] = [
  "yearly",
  "half_yearly",
  "quarterly",
  "monthly",
  "one_time",
]

interface FeeTypeDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  feeType: FeeType | null
}

export function FeeTypeDialog({ open, onOpenChange, feeType }: FeeTypeDialogProps) {
  const t = useTranslations("dues")
  const tc = useTranslations("common")
  const createFeeType = useCreateFeeType()
  const updateFeeType = useUpdateFeeType()
  const getErrorMessage = useErrorMessage()

  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [amount, setAmount] = useState("")
  const [interval, setInterval] = useState<FeeInterval>("yearly")
  const [isActive, setIsActive] = useState(true)

  useEffect(() => {
    if (!open) return
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setName(feeType?.name ?? "")
    setDescription(feeType?.description ?? "")
    setAmount(feeType?.amount ?? "")
    setInterval(feeType?.interval ?? "yearly")
    setIsActive(feeType?.is_active ?? true)
  }, [open, feeType])

  const intervalItems = INTERVALS.map((i) => ({
    value: i,
    label: t(`interval_${i}`),
  }))

  const normalizedAmount = amount.replace(",", ".")
  const canSubmit =
    name.trim() !== "" &&
    normalizedAmount !== "" &&
    !Number.isNaN(Number(normalizedAmount)) &&
    Number(normalizedAmount) >= 0

  const isPending = createFeeType.isPending || updateFeeType.isPending

  function handleSubmit() {
    const data = {
      name: name.trim(),
      description: description.trim() || null,
      amount: Number(normalizedAmount).toFixed(2),
      interval,
      is_active: isActive,
    }
    const options = {
      onSuccess: () => {
        toast.success(tc("saved"))
        onOpenChange(false)
      },
      onError: (err: unknown) => toast.error(getErrorMessage(err)),
    }
    if (feeType) {
      updateFeeType.mutate({ id: feeType.id, data }, options)
    } else {
      createFeeType.mutate(data, options)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {feeType ? t("editFeeType") : t("createFeeType")}
          </DialogTitle>
          <DialogDescription>{t("feeTypeDialogDescription")}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>{t("feeName")} *</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("feeNamePlaceholder")}
              autoFocus
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>{t("amount")} *</Label>
              <Input
                inputMode="decimal"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="120.00"
              />
            </div>
            <div className="space-y-2">
              <Label>{t("interval")}</Label>
              <Select
                items={intervalItems}
                value={interval}
                onValueChange={(v) => setInterval(v as FeeInterval)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {intervalItems.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-2">
            <Label>{t("feeDescription")}</Label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t("feeDescriptionPlaceholder")}
              className="min-h-16 text-sm"
            />
          </div>
          <div className="flex items-center justify-between">
            <Label>{t("active")}</Label>
            <Switch checked={isActive} onCheckedChange={setIsActive} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {tc("cancel")}
          </Button>
          <Button onClick={handleSubmit} disabled={!canSubmit || isPending}>
            {isPending ? tc("saving") : tc("save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
