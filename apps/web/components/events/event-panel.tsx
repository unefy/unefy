"use client"

import { useState } from "react"
import { useTranslations, useLocale } from "next-intl"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { SectionHeading } from "@/components/layout/section-heading"
import { ConfirmDialog } from "@/components/common/confirm-dialog"
import {
  useDeleteEvent,
  useEvent,
  useRegisterMember,
  useUnregisterMember,
  useUpdateEvent,
} from "@/hooks/use-events"
import { useMembers } from "@/hooks/use-members"
import { useErrorMessage } from "@/lib/errors"
import { formatDate } from "@/lib/date"
import { HugeiconsIcon } from "@hugeicons/react"
import { Cancel01Icon, Delete02Icon } from "@hugeicons/core-free-icons"

interface EventPanelProps {
  eventId: string
  onClose: () => void
}

export function EventPanel({ eventId, onClose }: EventPanelProps) {
  const t = useTranslations("events")
  const tc = useTranslations("common")
  const locale = useLocale()
  const getErrorMessage = useErrorMessage()

  const { data: event, isLoading } = useEvent(eventId)
  const { data: membersData } = useMembers({ per_page: 100, status: "active" })
  const updateEvent = useUpdateEvent()
  const deleteEvent = useDeleteEvent()
  const registerMember = useRegisterMember()
  const unregisterMember = useUnregisterMember()

  const [memberId, setMemberId] = useState("")
  const [confirmDelete, setConfirmDelete] = useState(false)

  const registeredMemberIds = new Set(
    event?.registrations.map((r) => r.member_id) ?? [],
  )
  const memberItems = (membersData?.data ?? [])
    .filter((m) => !registeredMemberIds.has(m.id))
    .map((m) => ({
      value: m.id,
      label: `${m.first_name} ${m.last_name}`,
    }))

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
        onClose()
      },
      onError: (err) => toast.error(getErrorMessage(err)),
    })
  }

  function handleRegister() {
    if (!memberId) return
    registerMember.mutate(
      { eventId, memberId },
      {
        onSuccess: (registration) => {
          toast.success(
            registration.status === "waitlist"
              ? t("addedToWaitlist")
              : tc("saved"),
          )
          setMemberId("")
        },
        onError: (err) => toast.error(getErrorMessage(err)),
      },
    )
  }

  if (isLoading || !event) {
    return (
      <div className="fixed right-0 top-0 z-30 flex h-screen w-[400px] flex-col bg-card">
        <div className="space-y-4 p-4">
          <div className="h-8 w-48 animate-pulse rounded bg-muted" />
          <div className="h-4 w-24 animate-pulse rounded bg-muted" />
        </div>
      </div>
    )
  }

  return (
    <div className="fixed right-0 top-0 z-30 flex h-screen w-[400px] flex-col bg-card">
      <div className="flex shrink-0 items-start justify-between px-4 pt-8 pb-2">
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-2xl font-bold tracking-tight">
            {event.title}
          </h2>
          <div className="mt-1 flex items-center gap-2">
            <Badge variant="secondary">{t(`type_${event.event_type}`)}</Badge>
            {event.competition_name && (
              <Badge variant="outline">{event.competition_name}</Badge>
            )}
            {event.status === "cancelled" && (
              <Badge variant="outline">{t("status_cancelled")}</Badge>
            )}
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
          aria-label={tc("cancel")}
        >
          <HugeiconsIcon icon={Cancel01Icon} size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        <div className="space-y-8">
          <div>
            <SectionHeading title={t("details")} description="" />
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-muted-foreground">{t("date")}</dt>
                <dd>{formatDate(event.starts_at, locale)}</dd>
              </div>
              {!event.all_day && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">{t("startTime")}</dt>
                  <dd>
                    {new Date(event.starts_at).toLocaleTimeString(locale, {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </dd>
                </div>
              )}
              {event.location && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">{t("location")}</dt>
                  <dd>{event.location}</dd>
                </div>
              )}
              {event.max_participants && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">
                    {t("maxParticipants")}
                  </dt>
                  <dd>{event.max_participants}</dd>
                </div>
              )}
            </dl>
            {event.description && (
              <p className="text-muted-foreground mt-3 text-sm whitespace-pre-wrap">
                {event.description}
              </p>
            )}
          </div>

          <div>
            <SectionHeading
              title={`${t("registrations")} (${event.registered_count}${
                event.max_participants ? ` / ${event.max_participants}` : ""
              })`}
              description=""
            />
            {event.registrations.length === 0 ? (
              <p className="text-muted-foreground text-sm">
                {t("noRegistrations")}
              </p>
            ) : (
              <div className="space-y-2">
                {event.registrations.map((registration) => (
                  <div
                    key={registration.id}
                    className="flex items-center justify-between rounded-lg border px-3 py-2"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="truncate text-sm font-medium">
                        {registration.member_name}
                      </span>
                      {registration.status === "waitlist" && (
                        <Badge variant="outline">{t("waitlist")}</Badge>
                      )}
                    </div>
                    <button
                      onClick={() =>
                        unregisterMember.mutate(
                          { eventId, registrationId: registration.id },
                          {
                            onSuccess: () => toast.success(tc("saved")),
                            onError: (err) =>
                              toast.error(getErrorMessage(err)),
                          },
                        )
                      }
                      disabled={unregisterMember.isPending}
                      className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
                      aria-label={tc("delete")}
                    >
                      <HugeiconsIcon icon={Delete02Icon} size={15} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-4 space-y-2">
              <Label>{t("registerMember")}</Label>
              <div className="flex gap-2">
                <Select
                  items={memberItems}
                  value={memberId || null}
                  onValueChange={(v) => setMemberId(v ?? "")}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder={t("selectMember")} />
                  </SelectTrigger>
                  <SelectContent>
                    {memberItems.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  size="sm"
                  onClick={handleRegister}
                  disabled={!memberId || registerMember.isPending}
                >
                  {registerMember.isPending ? tc("saving") : tc("create")}
                </Button>
              </div>
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleToggleStatus}
              disabled={updateEvent.isPending}
            >
              {event.status === "cancelled"
                ? t("reactivateEvent")
                : t("cancelEvent")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmDelete(true)}
            >
              {tc("delete")}
            </Button>
          </div>
        </div>
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
