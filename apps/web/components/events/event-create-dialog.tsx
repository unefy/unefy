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
  EMPTY_EVENT_FORM,
  EventFormFields,
  eventFormToPayload,
  type EventFormState,
} from "@/components/events/event-form-fields"
import { useCreateEvent } from "@/hooks/use-events"
import { useErrorMessage } from "@/lib/errors"

export function EventCreateDialog() {
  const t = useTranslations("events")
  const tc = useTranslations("common")
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<EventFormState>({ ...EMPTY_EVENT_FORM })
  const createEvent = useCreateEvent()
  const getErrorMessage = useErrorMessage()

  function handleChange<K extends keyof EventFormState>(
    name: K,
    value: EventFormState[K],
  ) {
    setForm((prev) => ({ ...prev, [name]: value }))
  }

  function handleClose() {
    setOpen(false)
    setForm({ ...EMPTY_EVENT_FORM })
  }

  function handleSubmit() {
    createEvent.mutate(eventFormToPayload(form), {
      onSuccess: () => {
        toast.success(tc("saved"))
        handleClose()
      },
      onError: (err) => toast.error(getErrorMessage(err)),
    })
  }

  const canSubmit = form.title.trim() !== "" && form.date !== ""

  return (
    <>
      <Button onClick={() => setOpen(true)}>{t("addEvent")}</Button>
      <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{t("createEvent")}</DialogTitle>
            <DialogDescription>{t("description")}</DialogDescription>
          </DialogHeader>
          <EventFormFields form={form} onChange={handleChange} />
          <DialogFooter>
            <Button variant="outline" onClick={handleClose}>
              {tc("cancel")}
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={!canSubmit || createEvent.isPending}
            >
              {createEvent.isPending ? tc("saving") : t("createEvent")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
