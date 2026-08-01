"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { createSportAction, updateSportAction } from "@/actions/admin-catalog"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogClose,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import type { Sport, SportModule } from "@/lib/types/admin"
import { PencilIcon, PlusIcon } from "lucide-react"

export function SportDialog({
  sport,
  modules,
}: {
  /** Omitted when creating. */
  sport?: Sport
  modules: SportModule[]
}) {
  const t = useTranslations("admin.sports.dialog")
  const tt = useTranslations("admin.toasts")
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  const [key, setKey] = useState(sport?.key ?? "")
  const [name, setName] = useState(sport?.name ?? "")
  const [description, setDescription] = useState(sport?.description ?? "")
  const [icon, setIcon] = useState(sport?.icon ?? "")
  const [sortOrder, setSortOrder] = useState(String(sport?.sort_order ?? 0))
  const [selected, setSelected] = useState<string[]>(sport?.modules ?? [])

  const isEdit = sport !== undefined

  function submit() {
    startTransition(async () => {
      const payload = {
        name,
        description: description || null,
        icon: icon || null,
        sort_order: Number(sortOrder) || 0,
        modules: selected,
      }
      const result = isEdit
        ? await updateSportAction(sport.id, payload)
        : await createSportAction({ key, ...payload })

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
            <Button size="sm">
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
          <DialogDescription>{t("description")}</DialogDescription>
        </DialogHeader>

        <DialogBody>
          <div className="space-y-2">
            <Label htmlFor="sport-key">{t("key")}</Label>
            <Input
              id="sport-key"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="shooting"
              // Other rows reference the key, so it is fixed after creation.
              disabled={isEdit}
            />
            <p className="text-xs text-muted-foreground">{t("keyHint")}</p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="sport-name">{t("name")}</Label>
            <Input
              id="sport-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Schießsport"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="sport-description">{t("descriptionField")}</Label>
            <Textarea
              id="sport-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="sport-icon">{t("icon")}</Label>
              <Input
                id="sport-icon"
                value={icon}
                onChange={(e) => setIcon(e.target.value)}
                placeholder="Target"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="sport-sort">{t("sortOrder")}</Label>
              <Input
                id="sport-sort"
                type="number"
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>{t("modules")}</Label>
            <p className="text-xs text-muted-foreground">{t("modulesHint")}</p>
            {modules.map((module) => (
              <label
                key={module.key}
                className="flex items-start gap-2 text-sm"
              >
                <Checkbox
                  checked={selected.includes(module.key)}
                  onCheckedChange={(checked) =>
                    setSelected((current) =>
                      checked
                        ? [...current, module.key]
                        : current.filter((m) => m !== module.key)
                    )
                  }
                />
                <span>{module.label}</span>
              </label>
            ))}
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
          <Button
            onClick={submit}
            disabled={pending || !name || (!isEdit && !key)}
          >
            {pending ? t("saving") : t("save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
