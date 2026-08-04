"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { saveRecordDetailAction } from "@/actions/shooting"
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
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type {
  ClubDiscipline,
  ShootingRecordDetail,
  WeaponCategory,
} from "@/lib/types/shooting"
import { WEAPON_CATEGORIES } from "@/lib/types/shooting"
import { TargetIcon } from "lucide-react"

/** Stands in for "nothing chosen", because a Select cannot hold null. */
const NONE = "__none__"

/**
 * What somebody shot at this attendance: discipline, weapon category, rounds.
 *
 * These three fields are what the range book prints and what a §14 certificate
 * describes beyond the bare day count, and until now nothing could write them —
 * the endpoint existed and no form reached it, so the book's columns were always
 * empty.
 *
 * No reason field, unlike a correction to the check-in itself. A discipline is a
 * detail *about* an evening, not a claim that somebody was present: getting it
 * wrong misfiles a round count, not an attendance. Every save is audited anyway.
 */
export function RecordDetailDialog({
  sessionId,
  recordId,
  memberName,
  detail,
  disciplines,
}: {
  sessionId: string
  recordId: string
  memberName: string
  detail: ShootingRecordDetail | undefined
  disciplines: ClubDiscipline[]
}) {
  const t = useTranslations("attendance.shooting")
  const tf = useTranslations("attendance.form")
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [pending, startTransition] = useTransition()

  const [discipline, setDiscipline] = useState(
    detail?.club_discipline_id ?? NONE
  )
  const [weapon, setWeapon] = useState<string>(detail?.weapon_category ?? NONE)
  const [rounds, setRounds] = useState(
    detail?.rounds_fired === null || detail?.rounds_fired === undefined
      ? ""
      : String(detail.rounds_fired)
  )

  function save() {
    startTransition(async () => {
      const result = await saveRecordDetailAction(sessionId, recordId, {
        club_discipline_id: discipline === NONE ? null : discipline,
        weapon_category: weapon === NONE ? null : weapon,
        // An empty field means "not known", which is a different statement from
        // "fired nothing" — and the latter is a legitimate entry.
        rounds_fired: rounds.trim() === "" ? null : Number(rounds),
      })
      if (result.success) {
        setOpen(false)
        toast.success(t("saved"))
        router.refresh()
      } else {
        toast.error(tf(`errors.${result.error}`))
      }
    })
  }

  const disciplineLabel = (id: string) =>
    id === NONE
      ? t("none")
      : (disciplines.find((d) => d.id === id)?.name ?? t("none"))

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        // Reopening after a cancel must show what is stored, not what was typed
        // and abandoned.
        if (!next) {
          setDiscipline(detail?.club_discipline_id ?? NONE)
          setWeapon(detail?.weapon_category ?? NONE)
          setRounds(
            detail?.rounds_fired === null || detail?.rounds_fired === undefined
              ? ""
              : String(detail.rounds_fired)
          )
        }
      }}
    >
      <DialogTrigger
        render={
          <Button
            variant="ghost"
            size="sm"
            aria-label={t("edit")}
            title={t("edit")}
          >
            <TargetIcon />
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("dialogTitle", { name: memberName })}</DialogTitle>
          <DialogDescription>{t("dialogDescription")}</DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor={`discipline-${recordId}`}>{t("discipline")}</Label>
            <Select
              value={discipline}
              onValueChange={(value) => setDiscipline(String(value))}
            >
              <SelectTrigger id={`discipline-${recordId}`} className="w-full">
                <SelectValue>
                  {(value: string) => disciplineLabel(value)}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value={NONE}>{t("none")}</SelectItem>
                  {disciplines.map((d) => (
                    <SelectItem key={d.id} value={d.id}>
                      {d.name}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
            {disciplines.length === 0 && (
              <p className="text-xs text-muted-foreground">
                {t("noDisciplines")}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor={`weapon-${recordId}`}>{t("weapon")}</Label>
            <Select
              value={weapon}
              onValueChange={(value) => setWeapon(String(value))}
            >
              <SelectTrigger id={`weapon-${recordId}`} className="w-full">
                <SelectValue>
                  {(value: string) =>
                    value === NONE ? t("none") : t(`weapons.${value}`)
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value={NONE}>{t("none")}</SelectItem>
                  {WEAPON_CATEGORIES.map((category: WeaponCategory) => (
                    <SelectItem key={category} value={category}>
                      {t(`weapons.${category}`)}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor={`rounds-${recordId}`}>{t("rounds")}</Label>
            <Input
              id={`rounds-${recordId}`}
              type="number"
              inputMode="numeric"
              min={0}
              max={100000}
              value={rounds}
              onChange={(event) => setRounds(event.target.value)}
              placeholder={t("roundsPlaceholder")}
            />
          </div>
        </DialogBody>

        <DialogFooter>
          <DialogClose
            render={
              <Button type="button" variant="outline">
                {tf("cancel")}
              </Button>
            }
          />
          <Button type="button" disabled={pending} onClick={save}>
            {pending ? tf("saving") : tf("save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
