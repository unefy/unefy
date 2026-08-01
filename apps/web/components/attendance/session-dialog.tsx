"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { createSessionAction, updateSessionAction } from "@/actions/attendance"
import { MemberSearch } from "@/components/attendance/member-search"
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
import type { AttendanceSession } from "@/lib/types/attendance"
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

/** Spontaneous is the common case: now, running until the end of the day. */
function defaultWindow() {
  const now = new Date()
  const end = new Date(now)
  end.setHours(23, 59, 0, 0)
  return {
    opens: toLocalInput(now.toISOString()),
    closes: toLocalInput(end.toISOString()),
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

export function SessionDialog({ session }: { session?: AttendanceSession }) {
  const t = useTranslations("attendance.form")
  const ts = useTranslations("attendance.search")
  const router = useRouter()
  const isEdit = session !== undefined

  const [open, setOpen] = useState(false)
  const initial = defaultWindow()
  const [opensAt, setOpensAt] = useState(
    isEdit ? toLocalInput(session.opens_at) : initial.opens
  )
  const [closesAt, setClosesAt] = useState(
    isEdit ? toLocalInput(session.closes_at) : initial.closes
  )
  const [supervisorId, setSupervisorId] = useState(
    session?.supervisor_member_id ?? ""
  )
  const [supervisorName, setSupervisorName] = useState(
    session?.supervisor_name ?? ""
  )

  const action = isEdit
    ? updateSessionAction.bind(null, session.id)
    : createSessionAction

  const [pending, startTransition] = useTransition()

  // The result is handled where it arrives rather than mirrored into state and
  // reacted to in an effect — closing the dialog is a consequence of the call,
  // not of a render.
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
                defaultValue={session?.title ?? ""}
                placeholder={t("placeholders.title")}
              />
            </Field>

            <Field id="location" label={t("fields.location")}>
              <Input
                id="location"
                name="location"
                maxLength={255}
                defaultValue={session?.location ?? ""}
                placeholder={t("placeholders.location")}
              />
            </Field>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field id="opens_at_local" label={t("fields.opensAt")}>
                <Input
                  id="opens_at_local"
                  type="datetime-local"
                  required
                  value={opensAt}
                  onChange={(event) => setOpensAt(event.target.value)}
                />
              </Field>
              <Field
                id="closes_at_local"
                label={t("fields.closesAt")}
                hint={t("hints.closesAt")}
              >
                <Input
                  id="closes_at_local"
                  type="datetime-local"
                  required
                  value={closesAt}
                  onChange={(event) => setClosesAt(event.target.value)}
                />
              </Field>
            </div>
            {/* The API wants an instant, the input gives wall-clock time. */}
            <input type="hidden" name="opens_at" value={toIso(opensAt)} />
            <input type="hidden" name="closes_at" value={toIso(closesAt)} />

            <div className="space-y-2">
              <Label>{t("fields.supervisor")}</Label>
              {supervisorId ? (
                <div className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
                  <span className="text-sm">{supervisorName}</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setSupervisorId("")
                      setSupervisorName("")
                    }}
                  >
                    {t("clear")}
                  </Button>
                </div>
              ) : (
                <MemberSearch
                  placeholder={ts("placeholder")}
                  actionLabel={t("choose")}
                  onSelect={(member) => {
                    setSupervisorId(member.id)
                    setSupervisorName(
                      `${member.first_name} ${member.last_name}`
                    )
                  }}
                />
              )}
              <p className="text-xs text-muted-foreground">
                {t("hints.supervisor")}
              </p>
              <input
                type="hidden"
                name="supervisor_member_id"
                value={supervisorId}
              />
            </div>

            {isEdit && (
              <Field
                id="reason"
                label={t("fields.reason")}
                hint={t("hints.reason")}
              >
                <Input id="reason" name="reason" maxLength={1000} />
              </Field>
            )}
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
