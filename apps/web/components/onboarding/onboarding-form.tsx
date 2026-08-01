"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"

import { createClubAction } from "@/actions/onboarding"
import { Button } from "@/components/ui/button"
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
import { Switch } from "@/components/ui/switch"
import type { PublicSport } from "@/lib/sports"
import { PlusIcon, XIcon } from "lucide-react"

type DivisionRow = { name: string; sport_key: string }

export function OnboardingForm({ sports }: { sports: PublicSport[] }) {
  const t = useTranslations("onboarding")
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)

  const [clubName, setClubName] = useState("")
  const [hasDivisions, setHasDivisions] = useState(false)
  const [sportKey, setSportKey] = useState(sports[0]?.key ?? "")
  const [divisions, setDivisions] = useState<DivisionRow[]>([
    { name: "", sport_key: sports[0]?.key ?? "" },
  ])

  function submit() {
    setError(null)
    startTransition(async () => {
      // Without divisions the club still gets exactly one, named after itself.
      // The concept simply stays hidden — same data shape either way.
      const payload = hasDivisions
        ? divisions.filter((d) => d.name.trim())
        : [{ name: clubName.trim(), sport_key: sportKey }]

      const result = await createClubAction({
        club_name: clubName,
        has_divisions: hasDivisions,
        divisions: payload,
      })

      if (result.success) {
        router.push("/")
      } else {
        setError(result.error)
      }
    })
  }

  const canSubmit =
    clubName.trim().length >= 2 &&
    (hasDivisions
      ? divisions.some((d) => d.name.trim()) &&
        divisions.every((d) => !d.name.trim() || d.sport_key)
      : Boolean(sportKey))

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Label htmlFor="club-name">{t("clubName")}</Label>
        <Input
          id="club-name"
          value={clubName}
          onChange={(e) => setClubName(e.target.value)}
          placeholder={t("clubNamePlaceholder")}
          autoFocus
        />
      </div>

      <div className="flex items-start justify-between gap-4 rounded-lg border p-4">
        <div className="space-y-1">
          <Label htmlFor="has-divisions">{t("hasDivisions")}</Label>
          <p className="text-sm text-muted-foreground">
            {t("hasDivisionsHint")}
          </p>
        </div>
        <Switch
          id="has-divisions"
          checked={hasDivisions}
          onCheckedChange={(checked) => setHasDivisions(Boolean(checked))}
        />
      </div>

      {hasDivisions ? (
        <div className="space-y-3">
          <Label>{t("divisions")}</Label>
          {divisions.map((division, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                value={division.name}
                onChange={(e) =>
                  setDivisions((rows) =>
                    rows.map((row, i) =>
                      i === index ? { ...row, name: e.target.value } : row
                    )
                  )
                }
                placeholder={t("divisionNamePlaceholder")}
              />
              <Select
                value={division.sport_key}
                onValueChange={(value) =>
                  setDivisions((rows) =>
                    rows.map((row, i) =>
                      i === index ? { ...row, sport_key: String(value) } : row
                    )
                  )
                }
              >
                <SelectTrigger aria-label={t("sport")}>
                  <SelectValue>
                    {(value: string) =>
                      sports.find((s) => s.key === value)?.name ?? ""
                    }
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {sports.map((sport) => (
                      <SelectItem key={sport.key} value={sport.key}>
                        {sport.name}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
              <Button
                variant="ghost"
                size="sm"
                aria-label={t("removeDivision")}
                disabled={divisions.length === 1}
                onClick={() =>
                  setDivisions((rows) => rows.filter((_, i) => i !== index))
                }
              >
                <XIcon />
              </Button>
            </div>
          ))}
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              setDivisions((rows) => [
                ...rows,
                { name: "", sport_key: sports[0]?.key ?? "" },
              ])
            }
          >
            <PlusIcon />
            {t("addDivision")}
          </Button>
        </div>
      ) : (
        <div className="space-y-2">
          <Label htmlFor="sport">{t("sport")}</Label>
          <Select
            value={sportKey}
            onValueChange={(value) => setSportKey(String(value))}
          >
            <SelectTrigger id="sport" className="w-full">
              <SelectValue>
                {(value: string) =>
                  sports.find((s) => s.key === value)?.name ?? ""
                }
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {sports.map((sport) => (
                  <SelectItem key={sport.key} value={sport.key}>
                    {sport.name}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
          <p className="text-sm text-muted-foreground">{t("sportHint")}</p>
        </div>
      )}

      {error && (
        <p className="text-sm text-destructive">{t(`errors.${error}`)}</p>
      )}

      <Button
        onClick={submit}
        disabled={pending || !canSubmit}
        className="w-full"
      >
        {pending ? t("creating") : t("submit")}
      </Button>
    </div>
  )
}
