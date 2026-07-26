"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useTranslations, useLocale } from "next-intl"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { DatePicker } from "@/components/ui/date-picker"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { SectionHeading } from "@/components/layout/section-heading"
import { ConfirmDialog } from "@/components/common/confirm-dialog"
import {
  useCompetitionSessions,
  useCreateSession,
  useDeleteSession,
} from "@/hooks/use-competitions"
import { useErrorMessage } from "@/lib/errors"
import { formatDate } from "@/lib/date"
import { HugeiconsIcon } from "@hugeicons/react"
import { Delete02Icon } from "@hugeicons/core-free-icons"

interface CompetitionSessionsSectionProps {
  competitionId: string
}

const EMPTY_SESSION_FORM = {
  name: "",
  date: "",
  location: "",
  discipline: "",
  createEvent: true,
  time: "",
}

export function CompetitionSessionsSection({
  competitionId,
}: CompetitionSessionsSectionProps) {
  const t = useTranslations("competitions")
  const tc = useTranslations("common")
  const locale = useLocale()
  const router = useRouter()
  const getErrorMessage = useErrorMessage()

  const { data, isLoading } = useCompetitionSessions(competitionId)
  const createSession = useCreateSession(competitionId)
  const deleteSession = useDeleteSession(competitionId)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [form, setForm] = useState({ ...EMPTY_SESSION_FORM })
  const [deleteId, setDeleteId] = useState<string | null>(null)

  function handleClose() {
    setDialogOpen(false)
    setForm({ ...EMPTY_SESSION_FORM })
  }

  function handleCreate() {
    createSession.mutate(
      {
        name: form.name.trim() || null,
        date: form.date,
        location: form.location.trim() || null,
        discipline: form.discipline.trim() || null,
        create_calendar_event: form.createEvent,
        starts_at:
          form.createEvent && form.time
            ? `${form.date}T${form.time}:00`
            : null,
      },
      {
        onSuccess: () => {
          toast.success(tc("saved"))
          handleClose()
        },
        onError: (err) => toast.error(getErrorMessage(err)),
      },
    )
  }

  function handleDelete() {
    if (!deleteId) return
    deleteSession.mutate(deleteId, {
      onSuccess: () => {
        toast.success(tc("saved"))
        setDeleteId(null)
      },
      onError: (err) => toast.error(getErrorMessage(err)),
    })
  }

  const sessions = data?.data ?? []

  return (
    <div>
      <div className="flex items-start justify-between">
        <SectionHeading
          title={t("sessions")}
          description={t("sessionsDescription")}
        />
        <Button variant="outline" size="sm" onClick={() => setDialogOpen(true)}>
          {t("addSession")}
        </Button>
      </div>

      {isLoading ? (
        <div className="h-32 animate-pulse rounded-xl bg-muted" />
      ) : sessions.length === 0 ? (
        <p className="text-muted-foreground py-6 text-center text-sm">
          {t("noSessions")}
        </p>
      ) : (
        <ul className="divide-y rounded-xl border">
          {sessions.map((session) => (
            <li
              key={session.id}
              className="flex items-center justify-between gap-3 px-4 py-3"
            >
              <Link
                href={`/competitions/${competitionId}/sessions/${session.id}`}
                className="min-w-0"
              >
                <p className="truncate font-medium hover:underline">
                  {session.name || formatDate(session.date, locale)}
                </p>
                <p className="text-muted-foreground truncate text-xs">
                  {formatDate(session.date, locale)}
                  {session.discipline ? ` · ${session.discipline}` : ""}
                  {session.location ? ` · ${session.location}` : ""}
                </p>
              </Link>
              <div className="flex shrink-0 items-center gap-2">
                {session.event_id && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => router.push(`/events/${session.event_id}`)}
                  >
                    {t("linkedEvent")}
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => setDeleteId(session.id)}
                  aria-label={tc("delete")}
                >
                  <HugeiconsIcon icon={Delete02Icon} size={14} />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Dialog open={dialogOpen} onOpenChange={(v) => !v && handleClose()}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t("addSession")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{t("sessionName")}</Label>
              <Input
                value={form.name}
                onChange={(e) =>
                  setForm((p) => ({ ...p, name: e.target.value }))
                }
                placeholder={t("sessionNamePlaceholder")}
              />
            </div>
            <div className="space-y-2">
              <Label>{t("sessionDate")} *</Label>
              <DatePicker
                value={form.date}
                onChange={(v) => setForm((p) => ({ ...p, date: v }))}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{t("sessionDiscipline")}</Label>
                <Input
                  value={form.discipline}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, discipline: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>{t("sessionLocation")}</Label>
                <Input
                  value={form.location}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, location: e.target.value }))
                  }
                />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <Label>{t("createLinkedEvent")}</Label>
              <Switch
                checked={form.createEvent}
                onCheckedChange={(v) =>
                  setForm((p) => ({ ...p, createEvent: v }))
                }
              />
            </div>
            {form.createEvent && (
              <div className="space-y-2">
                <Label>{t("sessionStartTime")}</Label>
                <Input
                  type="time"
                  value={form.time}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, time: e.target.value }))
                  }
                />
                <p className="text-muted-foreground text-xs">
                  {t("createLinkedEventHint")}
                </p>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={handleClose}>
              {tc("cancel")}
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!form.date || createSession.isPending}
            >
              {createSession.isPending ? tc("saving") : t("addSession")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteId !== null}
        onOpenChange={(v) => !v && setDeleteId(null)}
        title={t("deleteSession")}
        description={t("deleteSessionConfirm")}
        destructive
        pending={deleteSession.isPending}
        onConfirm={handleDelete}
      />
    </div>
  )
}
