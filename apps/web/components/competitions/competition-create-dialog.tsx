"use client"

import { useState } from "react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  CompetitionFormFields,
  competitionFormToPayload,
  EMPTY_COMPETITION_FORM,
  type CompetitionFormState,
} from "@/components/competitions/competition-form-fields"
import { useCreateCompetition } from "@/hooks/use-competitions"
import { useErrorMessage } from "@/lib/errors"

export function CompetitionCreateDialog() {
  const t = useTranslations("competitions")
  const tc = useTranslations("common")
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<CompetitionFormState>({
    ...EMPTY_COMPETITION_FORM,
  })
  const createCompetition = useCreateCompetition()
  const getErrorMessage = useErrorMessage()

  function handleChange<K extends keyof CompetitionFormState>(
    name: K,
    value: CompetitionFormState[K],
  ) {
    setForm((prev) => ({ ...prev, [name]: value }))
  }

  function handleClose() {
    setOpen(false)
    setForm({ ...EMPTY_COMPETITION_FORM })
  }

  function handleSubmit() {
    createCompetition.mutate(competitionFormToPayload(form), {
      onSuccess: () => {
        toast.success(tc("saved"))
        handleClose()
      },
      onError: (err) => toast.error(getErrorMessage(err)),
    })
  }

  const canSubmit = form.name.trim() !== "" && form.start_date !== ""

  return (
    <>
      <Button onClick={() => setOpen(true)}>{t("addCompetition")}</Button>
      <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{t("createCompetition")}</DialogTitle>
            <DialogDescription>{t("description")}</DialogDescription>
          </DialogHeader>
          <CompetitionFormFields form={form} onChange={handleChange} />
          <DialogFooter>
            <Button variant="outline" onClick={handleClose}>
              {tc("cancel")}
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={!canSubmit || createCompetition.isPending}
            >
              {createCompetition.isPending
                ? tc("saving")
                : t("createCompetition")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
