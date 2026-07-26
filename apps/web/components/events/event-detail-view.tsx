"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/layout/page-header"
import { SectionHeading } from "@/components/layout/section-heading"
import { ConfirmDialog } from "@/components/common/confirm-dialog"
import {
  EMPTY_EVENT_FORM,
  EventFormFields,
  eventFormToPayload,
  eventToFormState,
  type EventFormState,
} from "@/components/events/event-form-fields"
import { EventRegistrationsSection } from "@/components/events/event-registrations-section"
import { useDeleteEvent, useEvent, useUpdateEvent } from "@/hooks/use-events"
import { useErrorMessage } from "@/lib/errors"

interface EventDetailViewProps {
  eventId: string
}

export function EventDetailView({ eventId }: EventDetailViewProps) {
  const t = useTranslations("events")
  const tc = useTranslations("common")
  const router = useRouter()
  const getErrorMessage = useErrorMessage()

  const { data: event, isLoading } = useEvent(eventId)
  const updateEvent = useUpdateEvent()
  const deleteEvent = useDeleteEvent()

  const [form, setForm] = useState<EventFormState>({ ...EMPTY_EVENT_FORM })
  const [dirty, setDirty] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => {
    if (event) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setForm(eventToFormState(event))
      setDirty(false)
    }
  }, [event])

  function handleChange<K extends keyof EventFormState>(
    name: K,
    value: EventFormState[K],
  ) {
    setForm((prev) => ({ ...prev, [name]: value }))
    setDirty(true)
  }

  function handleSave() {
    updateEvent.mutate(
      { id: eventId, data: eventFormToPayload(form) },
      {
        onSuccess: () => {
          toast.success(tc("saved"))
          setDirty(false)
        },
        onError: (err) => toast.error(getErrorMessage(err)),
      },
    )
  }

  function handleToggleStatus() {
    if (!event) return
    const next = event.status === "cancelled" ? "scheduled" : "cancelled"
    updateEvent.mutate(
      { id: eventId, data: { status: next } },
      {
        onSuccess: () => toast.success(tc("saved")),
        onError: (err) => toast.error(getErrorMessage(err)),
      },
    )
  }

  function handleDelete() {
    deleteEvent.mutate(eventId, {
      onSuccess: () => {
        toast.success(tc("saved"))
        setConfirmDelete(false)
        router.push("/events")
      },
      onError: (err) => toast.error(getErrorMessage(err)),
    })
  }

  if (isLoading || !event) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <div className="h-64 animate-pulse rounded-2xl bg-muted" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={event.title}
        description={
          <span className="flex items-center gap-2">
            <Badge variant="secondary">{t(`type_${event.event_type}`)}</Badge>
            {event.competition_name && event.competition_id && (
              <Link href={`/competitions/${event.competition_id}`}>
                <Badge
                  variant="outline"
                  className="hover:bg-muted transition-colors"
                >
                  {event.competition_name} ↗
                </Badge>
              </Link>
            )}
            {event.status === "cancelled" && (
              <Badge variant="outline">{t("status_cancelled")}</Badge>
            )}
          </span>
        }
      >
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => router.push("/events")}>
            ← {t("title")}
          </Button>
          {dirty && (
            <Button onClick={handleSave} disabled={updateEvent.isPending}>
              {updateEvent.isPending ? tc("saving") : tc("save")}
            </Button>
          )}
          <Button
            variant="outline"
            onClick={handleToggleStatus}
            disabled={updateEvent.isPending}
          >
            {event.status === "cancelled"
              ? t("reactivateEvent")
              : t("cancelEvent")}
          </Button>
          <Button variant="destructive" onClick={() => setConfirmDelete(true)}>
            {t("deleteEvent")}
          </Button>
        </div>
      </PageHeader>

      <div className="grid gap-10 lg:grid-cols-2">
        <div>
          <SectionHeading title={t("details")} description="" />
          <EventFormFields form={form} onChange={handleChange} />
        </div>
        <EventRegistrationsSection event={event} />
      </div>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={t("deleteEvent")}
        description={t("deleteEventConfirm", { title: event.title })}
        destructive
        pending={deleteEvent.isPending}
        onConfirm={handleDelete}
      />
    </div>
  )
}
