"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import {
  createDisciplineAction,
  updateDisciplineAction,
} from "@/actions/admin-catalog"
import { Button } from "@/components/ui/button"
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
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import type { CatalogDiscipline, Sport } from "@/lib/types/admin"
import { PencilIcon, PlusIcon } from "lucide-react"

/** Kept in sync with `SCORING_MODES` in `app/schemas/catalog_admin.py`. */
const SCORING_MODES = ["highest_wins", "lowest_wins", "fastest_time"] as const

export function DisciplineDialog({
  sports,
  discipline,
  defaultSportId,
}: {
  sports: Sport[]
  /** Omitted when creating. */
  discipline?: CatalogDiscipline
  defaultSportId?: string
}) {
  const t = useTranslations("admin.disciplines.dialog")
  const tt = useTranslations("admin.toasts")
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  const isEdit = discipline !== undefined
  const [form, setForm] = useState({
    sport_id: discipline?.sport_id ?? defaultSportId ?? sports[0]?.id ?? "",
    slug: discipline?.slug ?? "",
    name: discipline?.name ?? "",
    short_name: discipline?.short_name ?? "",
    federation: discipline?.federation ?? "",
    federation_id: discipline?.federation_id ?? "",
    category: discipline?.category ?? "",
    distance: discipline?.distance ?? "",
    caliber: discipline?.caliber ?? "",
    scoring_unit: discipline?.scoring_unit ?? "Ringe",
    scoring_mode: discipline?.scoring_mode ?? "highest_wins",
    shot_count: discipline?.shot_count ? String(discipline.shot_count) : "",
    description: discipline?.description ?? "",
  })

  function set(field: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function submit() {
    startTransition(async () => {
      const payload: Record<string, unknown> = {
        sport_id: form.sport_id,
        name: form.name,
        short_name: form.short_name || null,
        federation: form.federation,
        federation_id: form.federation_id || null,
        category: form.category,
        distance: form.distance || null,
        caliber: form.caliber || null,
        scoring_unit: form.scoring_unit,
        scoring_mode: form.scoring_mode,
        shot_count: form.shot_count ? Number(form.shot_count) : null,
        description: form.description || null,
      }
      // The slug is the catalog's stable identity — set once, never changed.
      if (!isEdit) payload.slug = form.slug

      const result = isEdit
        ? await updateDisciplineAction(discipline.id, payload)
        : await createDisciplineAction(payload)

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

  const field = (
    id: keyof typeof form,
    label: string,
    placeholder?: string
  ) => (
    <div className="space-y-2">
      <Label htmlFor={`discipline-${id}`}>{label}</Label>
      <Input
        id={`discipline-${id}`}
        value={form[id]}
        onChange={(e) => set(id, e.target.value)}
        placeholder={placeholder}
      />
    </div>
  )

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
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? t("editTitle") : t("createTitle")}
          </DialogTitle>
          <DialogDescription>{t("description")}</DialogDescription>
        </DialogHeader>

        <DialogBody>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="discipline-sport">{t("sport")}</Label>
              <Select
                value={form.sport_id}
                onValueChange={(value) => set("sport_id", String(value))}
              >
                <SelectTrigger id="discipline-sport" className="w-full">
                  <SelectValue>
                    {(value: string) =>
                      sports.find((s) => s.id === value)?.name ?? ""
                    }
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {sports.map((sport) => (
                      <SelectItem key={sport.id} value={sport.id}>
                        {sport.name}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="discipline-slug">{t("slug")}</Label>
              <Input
                id="discipline-slug"
                value={form.slug}
                onChange={(e) => set("slug", e.target.value)}
                placeholder="dsb-1-40"
                disabled={isEdit}
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {field("name", t("name"), "Luftgewehr")}
            {field("short_name", t("shortName"), "LG 10m")}
            {field("federation", t("federation"), "DSB")}
            {field("federation_id", t("federationId"), "1.40")}
            {field("category", t("category"), "Luftdruck")}
            {field("distance", t("distance"), "10m")}
            {field("caliber", t("caliber"), "4.5mm")}
            {field("scoring_unit", t("scoringUnit"), "Ringe")}
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="discipline-mode">{t("scoringMode")}</Label>
              <Select
                value={form.scoring_mode}
                onValueChange={(value) => set("scoring_mode", String(value))}
              >
                <SelectTrigger id="discipline-mode" className="w-full">
                  <SelectValue>
                    {(value: string) => t(`modes.${value}`)}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {SCORING_MODES.map((mode) => (
                      <SelectItem key={mode} value={mode}>
                        {t(`modes.${mode}`)}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">{t("modeHint")}</p>
            </div>
            {field("shot_count", t("shotCount"), "40")}
          </div>

          <div className="space-y-2">
            <Label htmlFor="discipline-description">
              {t("descriptionField")}
            </Label>
            <Textarea
              id="discipline-description"
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
            />
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
            disabled={
              pending ||
              !form.name ||
              !form.federation ||
              !form.category ||
              (!isEdit && !form.slug)
            }
          >
            {pending ? t("saving") : t("save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
