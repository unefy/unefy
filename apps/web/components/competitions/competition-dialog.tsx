"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import {
  createCompetitionAction,
  updateCompetitionAction,
} from "@/actions/competitions"
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
import { Textarea } from "@/components/ui/textarea"
import {
  COMPETITION_TYPE_KEYS,
  SCORING_MODE_KEYS,
  type Competition,
} from "@/lib/types/competition"
import { PencilIcon, PlusIcon } from "lucide-react"

function Field({
  id,
  label,
  hint,
  children,
}: {
  id: string
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

export function CompetitionDialog({
  competition,
  /** Disciplines the club actually offers — free text stays possible. */
  suggestions = [],
}: {
  competition?: Competition
  suggestions?: string[]
}) {
  const t = useTranslations("competitions.form")
  const tc = useTranslations("competitions")
  const router = useRouter()
  const isEdit = competition !== undefined

  const [open, setOpen] = useState(false)
  const [type, setType] = useState(competition?.competition_type ?? "competition")
  const [mode, setMode] = useState(competition?.scoring_mode ?? "highest_wins")
  const [pending, startTransition] = useTransition()

  const action = isEdit
    ? updateCompetitionAction.bind(null, competition.id)
    : createCompetitionAction

  function submit(formData: FormData) {
    startTransition(async () => {
      const result = await action(undefined, formData)
      if (result.success) {
        setOpen(false)
        toast.success(isEdit ? t("savedToast") : t("createdToast"))
        router.refresh()
      } else {
        toast.error(tc(`errors.${result.error}`))
      }
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          isEdit ? (
            <Button variant="outline" size="sm">
              <PencilIcon />
              {t("edit")}
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
            <DialogDescription>{t("description")}</DialogDescription>
          </DialogHeader>

          <DialogBody className="space-y-4">
            <Field id="name" label={t("fields.name")}>
              <Input
                id="name"
                name="name"
                required
                maxLength={255}
                defaultValue={competition?.name ?? ""}
                placeholder={t("placeholders.name")}
              />
            </Field>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field id="competition_type" label={t("fields.type")}>
                <Select
                  value={type}
                  onValueChange={(value) => setType(String(value))}
                >
                  <SelectTrigger id="competition_type" className="w-full">
                    <SelectValue>
                      {(value: string) => tc(`types.${value || "competition"}`)}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {COMPETITION_TYPE_KEYS.map((key) => (
                      <SelectItem key={key} value={key}>
                        {tc(`types.${key}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <input type="hidden" name="competition_type" value={type} />
              </Field>

              <Field
                id="disciplines"
                label={t("fields.disciplines")}
                hint={
                  suggestions.length > 0
                    ? t("hints.disciplinesWithSuggestions", {
                        examples: suggestions.slice(0, 3).join(", "),
                      })
                    : t("hints.disciplines")
                }
              >
                <Input
                  id="disciplines"
                  name="disciplines"
                  defaultValue={competition?.disciplines?.join(", ") ?? ""}
                />
              </Field>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field id="start_date" label={t("fields.startDate")}>
                <Input
                  id="start_date"
                  name="start_date"
                  type="date"
                  required
                  defaultValue={competition?.start_date ?? ""}
                />
              </Field>
              <Field
                id="end_date"
                label={t("fields.endDate")}
                hint={t("hints.endDate")}
              >
                <Input
                  id="end_date"
                  name="end_date"
                  type="date"
                  defaultValue={competition?.end_date ?? ""}
                />
              </Field>
            </div>

            {/*
              The two fields that keep this sport-agnostic: what the number is
              called, and whether more of it is better.
            */}
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                id="scoring_unit"
                label={t("fields.scoringUnit")}
                hint={t("hints.scoringUnit")}
              >
                <Input
                  id="scoring_unit"
                  name="scoring_unit"
                  required
                  maxLength={50}
                  defaultValue={competition?.scoring_unit ?? "Punkte"}
                />
              </Field>
              <Field id="scoring_mode" label={t("fields.scoringMode")}>
                <Select
                  value={mode}
                  onValueChange={(value) => setMode(String(value))}
                >
                  <SelectTrigger id="scoring_mode" className="w-full">
                    <SelectValue>
                      {(value: string) =>
                        tc(`modes.${value || "highest_wins"}`)
                      }
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {SCORING_MODE_KEYS.map((key) => (
                      <SelectItem key={key} value={key}>
                        {tc(`modes.${key}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <input type="hidden" name="scoring_mode" value={mode} />
              </Field>
            </div>

            <Field id="description" label={t("fields.description")}>
              <Textarea
                id="description"
                name="description"
                rows={2}
                maxLength={5000}
                defaultValue={competition?.description ?? ""}
              />
            </Field>
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
