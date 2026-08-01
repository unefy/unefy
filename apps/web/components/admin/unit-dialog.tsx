"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { createUnitAction, updateUnitAction } from "@/actions/admin-catalog"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { CatalogUnit } from "@/lib/types/admin"
import { PencilIcon, PlusIcon } from "lucide-react"

export function UnitDialog({
  sportId,
  unit,
}: {
  sportId: string
  /** Omitted when creating. */
  unit?: CatalogUnit
}) {
  const t = useTranslations("admin.units.dialog")
  const tt = useTranslations("admin.toasts")
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  const [name, setName] = useState(unit?.name ?? "")
  const [symbol, setSymbol] = useState(unit?.symbol ?? "")
  const [sortOrder, setSortOrder] = useState(String(unit?.sort_order ?? 0))

  const isEdit = unit !== undefined

  function submit() {
    startTransition(async () => {
      const payload = {
        name,
        symbol: symbol || null,
        sort_order: Number(sortOrder) || 0,
      }
      const result = isEdit
        ? await updateUnitAction(unit.id, payload)
        : await createUnitAction({ sport_id: sportId, ...payload })

      if (result.success) {
        setOpen(false)
        setError(null)
        toast.success(isEdit ? tt("saved") : tt("created"))
        router.refresh()
      } else {
        setError(result.error)
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
            <Button size="sm" variant="outline">
              <PlusIcon />
              {t("create")}
            </Button>
          )
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isEdit ? t("editTitle") : t("createTitle")}
          </DialogTitle>
        </DialogHeader>

        <DialogBody>
          <div className="space-y-2">
            <Label htmlFor="unit-name">{t("name")}</Label>
            <Input
              id="unit-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ringe"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="unit-symbol">{t("symbol")}</Label>
              <Input
                id="unit-symbol"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                placeholder="Pkt."
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="unit-sort">{t("sortOrder")}</Label>
              <Input
                id="unit-sort"
                type="number"
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value)}
              />
            </div>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </DialogBody>

        <DialogFooter>
          <DialogClose
            render={
              <Button type="button" variant="outline">
                {t("cancel")}
              </Button>
            }
          />
          <Button onClick={submit} disabled={pending || !name}>
            {pending ? t("saving") : t("save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
