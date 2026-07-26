"use client"

import { useState } from "react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
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
import { useGenerateDues } from "@/hooks/use-dues"
import { useErrorMessage } from "@/lib/errors"

const CURRENT_YEAR = new Date().getFullYear()
const YEARS = Array.from({ length: 3 }, (_, i) => CURRENT_YEAR + 1 - i)

export function GenerateDuesDialog() {
  const t = useTranslations("dues")
  const tc = useTranslations("common")
  const [open, setOpen] = useState(false)
  const [year, setYear] = useState(String(CURRENT_YEAR))
  const generate = useGenerateDues()
  const getErrorMessage = useErrorMessage()

  const yearItems = YEARS.map((y) => ({ value: String(y), label: String(y) }))

  function handleGenerate() {
    generate.mutate(Number(year), {
      onSuccess: ({ created }) => {
        toast.success(t("generateSuccess", { count: created }))
        setOpen(false)
      },
      onError: (err) => toast.error(getErrorMessage(err)),
    })
  }

  return (
    <>
      <Button onClick={() => setOpen(true)}>{t("generate")}</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t("generateTitle")}</DialogTitle>
            <DialogDescription>{t("generateDescription")}</DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <Label>{t("year")}</Label>
            <Select
              items={yearItems}
              value={year}
              onValueChange={(v) => setYear(v ?? String(CURRENT_YEAR))}
            >
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {yearItems.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              {tc("cancel")}
            </Button>
            <Button onClick={handleGenerate} disabled={generate.isPending}>
              {generate.isPending ? tc("saving") : t("generateRun")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
