"use client"

import { useState, useTransition } from "react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { setClubSportsAction } from "@/actions/club"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { PublicSport } from "@/lib/sports"
import type { ClubSport } from "@/lib/types/club"

/**
 * Which sports the club runs — and thereby which modules exist for it.
 *
 * The same choice the onboarding makes, editable later: a club adds a
 * division, and the shooting section should not require re-founding it.
 */
export function ClubSportsForm({
  catalog,
  active,
  canEdit,
}: {
  catalog: PublicSport[]
  active: ClubSport[]
  canEdit: boolean
}) {
  const t = useTranslations("clubSettings.sports")
  const [pending, startTransition] = useTransition()
  const [selected, setSelected] = useState<string[]>(active.map((s) => s.id))
  const [primary, setPrimary] = useState(
    active.find((s) => s.is_primary)?.id ?? active[0]?.id ?? ""
  )

  function toggle(id: string, checked: boolean) {
    const next = checked
      ? [...selected, id]
      : selected.filter((existing) => existing !== id)
    setSelected(next)
    if (!next.includes(primary)) setPrimary(next[0] ?? "")
  }

  function save() {
    startTransition(async () => {
      const result = await setClubSportsAction(selected, primary)
      if (result.success) {
        toast.success(t("savedToast"))
      } else {
        toast.error(t(`errors.${result.error}`))
      }
    })
  }

  const nameById = new Map(catalog.map((sport) => [sport.id, sport.name]))

  return (
    <section className="space-y-4 rounded-md border p-4">
      <div className="space-y-2">
        {catalog.map((sport) => (
          <label key={sport.id} className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={selected.includes(sport.id)}
              disabled={!canEdit}
              onCheckedChange={(checked) => toggle(sport.id, checked === true)}
            />
            {sport.name}
          </label>
        ))}
      </div>

      <div className="max-w-xs space-y-2">
        <Label htmlFor="primary-sport">{t("primary")}</Label>
        <Select
          value={primary}
          onValueChange={(value) => setPrimary(String(value))}
        >
          <SelectTrigger
            id="primary-sport"
            className="w-full"
            disabled={!canEdit || selected.length === 0}
          >
            <SelectValue>
              {(value: string) => nameById.get(value) ?? t("primaryNone")}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {selected.map((id) => (
                <SelectItem key={id} value={id}>
                  {nameById.get(id) ?? id}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">{t("primaryHint")}</p>
      </div>

      {canEdit && (
        <Button
          onClick={save}
          disabled={pending || selected.length === 0 || !primary}
        >
          {pending ? t("saving") : t("save")}
        </Button>
      )}
    </section>
  )
}
