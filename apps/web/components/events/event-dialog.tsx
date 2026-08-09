"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { createEventAction, updateEventAction } from "@/actions/events"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
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
import { EVENT_TYPE_KEYS, type ClubEvent } from "@/lib/types/event"
import { PencilIcon, PlusIcon } from "lucide-react"

/** `datetime-local` speaks local wall-clock time; the API speaks UTC. */
function toIso(local: string): string {
  if (!local) return ""
  const date = new Date(local)
  return Number.isNaN(date.getTime()) ? "" : date.toISOString()
}

function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return ""
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ""
  const pad = (value: number) => String(value).padStart(2, "0")
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

/** The common case: the next full hour, running two hours. */
function defaultWindow() {
  const start = new Date()
  start.setMinutes(0, 0, 0)
  start.setHours(start.getHours() + 1)
  const end = new Date(start)
  end.setHours(end.getHours() + 2)
  return {
    starts: toLocalInput(start.toISOString()),
    ends: toLocalInput(end.toISOString()),
  }
}

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

export function EventDialog({ event }: { event?: ClubEvent }) {
  const t = useTranslations("events.form")
  const te = useTranslations("events")
  const router = useRouter()
  const isEdit = event !== undefined

  const [open, setOpen] = useState(false)
  const initial = defaultWindow()
  const [startsAt, setStartsAt] = useState(
    isEdit ? toLocalInput(event.starts_at) : initial.starts
  )
  const [endsAt, setEndsAt] = useState(
    isEdit ? toLocalInput(event.ends_at) : initial.ends
  )
  const [deadline, setDeadline] = useState(
    isEdit ? toLocalInput(event.registration_deadline) : ""
  )
  const [eventType, setEventType] = useState(event?.event_type ?? "other")
  const [allDay, setAllDay] = useState(event?.all_day ?? false)
  // Controlled so the registration fields can appear with the checkbox rather
  // than sitting there greyed out for events nobody signs up to.
  const [registration, setRegistration] = useState(
    event?.registration_required ?? false
  )

  const action = isEdit
    ? updateEventAction.bind(null, event.id)
    : createEventAction

  const [pending, startTransition] = useTransition()

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
            <Field id="title" label={t("fields.title")}>
              <Input
                id="title"
                name="title"
                required
                maxLength={255}
                defaultValue={event?.title ?? ""}
                placeholder={t("placeholders.title")}
              />
            </Field>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field id="event_type" label={t("fields.type")}>
                <Select
                  value={eventType}
                  onValueChange={(value) => setEventType(String(value))}
                >
                  <SelectTrigger id="event_type" className="w-full">
                    <SelectValue>
                      {(value: string) => te(`types.${value || "other"}`)}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {EVENT_TYPE_KEYS.map((key) => (
                      <SelectItem key={key} value={key}>
                        {te(`types.${key}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <input type="hidden" name="event_type" value={eventType} />
              </Field>

              <Field id="location" label={t("fields.location")}>
                <Input
                  id="location"
                  name="location"
                  maxLength={255}
                  defaultValue={event?.location ?? ""}
                  placeholder={t("placeholders.location")}
                />
              </Field>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field id="starts_at_local" label={t("fields.startsAt")}>
                <Input
                  id="starts_at_local"
                  type="datetime-local"
                  required
                  value={startsAt}
                  onChange={(event) => setStartsAt(event.target.value)}
                />
              </Field>
              <Field
                id="ends_at_local"
                label={t("fields.endsAt")}
                hint={t("hints.endsAt")}
              >
                <Input
                  id="ends_at_local"
                  type="datetime-local"
                  value={endsAt}
                  onChange={(event) => setEndsAt(event.target.value)}
                />
              </Field>
            </div>
            {/* The API wants an instant, the input gives wall-clock time. */}
            <input type="hidden" name="starts_at" value={toIso(startsAt)} />
            <input type="hidden" name="ends_at" value={toIso(endsAt)} />

            {/* Checkboxes carry their value in a hidden input: an unchecked box
                never reaches FormData, so the form could not tell "off" from
                "field not rendered". */}
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={allDay}
                onCheckedChange={(checked) => setAllDay(checked === true)}
              />
              {t("fields.allDay")}
            </label>
            <input type="hidden" name="all_day" value={String(allDay)} />

            <Field id="description" label={t("fields.description")}>
              <Textarea
                id="description"
                name="description"
                maxLength={5000}
                rows={3}
                defaultValue={event?.description ?? ""}
              />
            </Field>

            <div className="space-y-4 rounded-md border p-4">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={registration}
                  onCheckedChange={(checked) =>
                    setRegistration(checked === true)
                  }
                />
                {t("fields.registrationRequired")}
              </label>
              <input
                type="hidden"
                name="registration_required"
                value={String(registration)}
              />

              {registration && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field
                    id="max_participants"
                    label={t("fields.maxParticipants")}
                    hint={t("hints.maxParticipants")}
                  >
                    <Input
                      id="max_participants"
                      name="max_participants"
                      type="number"
                      min={1}
                      defaultValue={event?.max_participants ?? ""}
                    />
                  </Field>
                  <Field
                    id="registration_deadline_local"
                    label={t("fields.deadline")}
                    hint={t("hints.deadline")}
                  >
                    <Input
                      id="registration_deadline_local"
                      type="datetime-local"
                      value={deadline}
                      onChange={(event) => setDeadline(event.target.value)}
                    />
                  </Field>
                </div>
              )}
            </div>
            <input
              type="hidden"
              name="registration_deadline"
              value={registration ? toIso(deadline) : ""}
            />
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
