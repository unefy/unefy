"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { createDivisionAction, updateDivisionAction } from "@/actions/divisions"
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
import type { ClubSport } from "@/lib/types/club"
import type { ClubDivision } from "@/lib/types/functions"
import { PencilIcon, PlusIcon } from "lucide-react"

/** Sentinel for "no sport yet" — Select does not allow an empty value. */
const NONE = "none"

export function DivisionDialog({
  division,
  sports,
}: {
  division?: ClubDivision
  /** The club's own sports; a division may carry no other. */
  sports: ClubSport[]
}) {
  const t = useTranslations("clubSettings.divisions")
  const router = useRouter()
  const isEdit = division !== undefined

  const [open, setOpen] = useState(false)
  const [sportId, setSportId] = useState(division?.sport_id ?? NONE)
  const [pending, startTransition] = useTransition()

  const action = isEdit
    ? updateDivisionAction.bind(null, division.id)
    : createDivisionAction

  function submit(formData: FormData) {
    startTransition(async () => {
      const result = await action(undefined, formData)
      if (result.success) {
        setOpen(false)
        toast.success(isEdit ? t("savedToast") : t("createdToast"))
        router.refresh()
      } else {
        toast.error(t(`errors.${result.error}`))
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
            <DialogDescription>{t("dialogDescription")}</DialogDescription>
          </DialogHeader>

          <DialogBody className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">{t("fields.name")}</Label>
              <Input
                id="name"
                name="name"
                required
                maxLength={255}
                defaultValue={division?.name ?? ""}
                placeholder={t("placeholder")}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="sport_id">{t("fields.sport")}</Label>
              <Select
                value={sportId}
                onValueChange={(value) => setSportId(String(value))}
              >
                <SelectTrigger id="sport_id" className="w-full">
                  <SelectValue>
                    {(value: string) =>
                      sports.find((sport) => sport.id === value)?.name ??
                      t("noSport")
                    }
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>{t("noSport")}</SelectItem>
                  {sports.map((sport) => (
                    <SelectItem key={sport.id} value={sport.id}>
                      {sport.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {/* The sentinel never reaches the API; empty means "none". */}
              <input
                type="hidden"
                name="sport_id"
                value={sportId === NONE ? "" : sportId}
              />
              <p className="text-xs text-muted-foreground">
                {t("hints.sport")}
              </p>
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
