"use client"

import { useTranslations } from "next-intl"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { DatePicker } from "@/components/ui/date-picker"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type {
  Competition,
  CompetitionCreate,
  CompetitionType,
} from "@/lib/types/competition"

export const COMPETITION_TYPES: CompetitionType[] = [
  "competition",
  "league",
  "training",
]

const SCORING_MODES = ["highest_wins", "lowest_wins"] as const

export interface CompetitionFormState {
  name: string
  competition_type: CompetitionType
  start_date: string
  end_date: string
  scoring_mode: "highest_wins" | "lowest_wins"
  scoring_unit: string
  disciplines: string
  description: string
}

export const EMPTY_COMPETITION_FORM: CompetitionFormState = {
  name: "",
  competition_type: "competition",
  start_date: "",
  end_date: "",
  scoring_mode: "highest_wins",
  scoring_unit: "Punkte",
  disciplines: "",
  description: "",
}

export function competitionToFormState(c: Competition): CompetitionFormState {
  return {
    name: c.name,
    competition_type: c.competition_type,
    start_date: c.start_date,
    end_date: c.end_date ?? "",
    scoring_mode: c.scoring_mode,
    scoring_unit: c.scoring_unit,
    disciplines: (c.disciplines ?? []).join(", "),
    description: c.description ?? "",
  }
}

export function competitionFormToPayload(
  form: CompetitionFormState,
): CompetitionCreate {
  const disciplines = form.disciplines
    .split(",")
    .map((d) => d.trim())
    .filter(Boolean)
  return {
    name: form.name.trim(),
    competition_type: form.competition_type,
    start_date: form.start_date,
    end_date: form.end_date || null,
    scoring_mode: form.scoring_mode,
    scoring_unit: form.scoring_unit.trim() || "Punkte",
    disciplines: disciplines.length > 0 ? disciplines : null,
    description: form.description.trim() || null,
  }
}

interface CompetitionFormFieldsProps {
  form: CompetitionFormState
  onChange: <K extends keyof CompetitionFormState>(
    name: K,
    value: CompetitionFormState[K],
  ) => void
}

export function CompetitionFormFields({
  form,
  onChange,
}: CompetitionFormFieldsProps) {
  const t = useTranslations("competitions")

  const typeItems = COMPETITION_TYPES.map((type) => ({
    value: type,
    label: t(`type_${type}`),
  }))
  const scoringItems = SCORING_MODES.map((mode) => ({
    value: mode,
    label: t(`scoring_${mode}`),
  }))

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>{t("name")} *</Label>
        <Input
          value={form.name}
          onChange={(e) => onChange("name", e.target.value)}
          placeholder={t("namePlaceholder")}
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{t("type")}</Label>
          <Select
            items={typeItems}
            value={form.competition_type}
            onValueChange={(v) =>
              onChange("competition_type", v as CompetitionType)
            }
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {typeItems.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>{t("scoringMode")}</Label>
          <Select
            items={scoringItems}
            value={form.scoring_mode}
            onValueChange={(v) =>
              onChange("scoring_mode", v as "highest_wins" | "lowest_wins")
            }
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {scoringItems.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{t("startDate")} *</Label>
          <DatePicker
            value={form.start_date}
            onChange={(v) => onChange("start_date", v)}
          />
        </div>
        <div className="space-y-2">
          <Label>{t("endDate")}</Label>
          <DatePicker
            value={form.end_date}
            onChange={(v) => onChange("end_date", v)}
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{t("scoringUnit")}</Label>
          <Input
            value={form.scoring_unit}
            onChange={(e) => onChange("scoring_unit", e.target.value)}
            placeholder={t("scoringUnitPlaceholder")}
          />
        </div>
        <div className="space-y-2">
          <Label>{t("disciplines")}</Label>
          <Input
            value={form.disciplines}
            onChange={(e) => onChange("disciplines", e.target.value)}
            placeholder={t("disciplinesPlaceholder")}
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>{t("competitionDescription")}</Label>
        <Textarea
          value={form.description}
          onChange={(e) => onChange("description", e.target.value)}
          placeholder={t("competitionDescriptionPlaceholder")}
          className="min-h-16 text-sm"
        />
      </div>
    </div>
  )
}
