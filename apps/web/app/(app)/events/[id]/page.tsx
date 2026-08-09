import Link from "next/link"
import { notFound } from "next/navigation"
import { getLocale, getTranslations } from "next-intl/server"

import { cancelEventAction, deleteEventAction } from "@/actions/events"
import { AttendancePanel } from "@/components/events/attendance-panel"
import { EventDialog } from "@/components/events/event-dialog"
import { RegistrationsPanel } from "@/components/events/registrations-panel"
import { SelfRegistration } from "@/components/events/self-registration"
import { ConfirmAction } from "@/components/ui/confirm-action"
import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { getClubTimeZone } from "@/lib/attendance"
import { getSession } from "@/lib/auth"
import { getEvent } from "@/lib/events"
import { formatDate, formatDateTime, formatTime } from "@/lib/time"
import {
  ArrowLeftIcon,
  BanIcon,
  Trash2Icon,
  TrophyIcon,
} from "lucide-react"

const BOARD_ROLES = ["owner", "admin", "board"]

function Fact({
  label,
  value,
  children,
}: {
  label: string
  value?: string | null
  children?: React.ReactNode
}) {
  return (
    <div className="space-y-1">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm">{children ?? (value?.trim() ? value : "—")}</dd>
    </div>
  )
}

export default async function EventPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const [t, locale, timeZone, session, { id }] = await Promise.all([
    getTranslations("events"),
    getLocale(),
    getClubTimeZone(),
    getSession(),
    params,
  ])

  const event = await getEvent(id).catch(() => null)
  if (!event) notFound()

  const canManage = BOARD_ROLES.includes(session?.role ?? "")
  const cancelled = event.status === "cancelled"
  const past =
    new Date(event.ends_at ?? event.starts_at).getTime() <
    new Date().getTime()

  return (
    <>
      <div className="space-y-3">
        <Link
          href="/events"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeftIcon className="size-4" />
          {t("detail.back")}
        </Link>

        <div className="flex flex-wrap items-center gap-3">
          <HeaderScrollTitle title={event.title} />
          <h1 className="text-2xl font-semibold tracking-tight">
            {event.title}
          </h1>
          <Badge variant="secondary">{t(`types.${event.event_type}`)}</Badge>
          {cancelled && (
            <Badge variant="destructive">{t("status.cancelled")}</Badge>
          )}
          {event.competition_name && (
            <Badge variant="outline" className="gap-1">
              <TrophyIcon className="size-3" />
              {event.competition_name}
            </Badge>
          )}

          <div className="ms-auto flex flex-wrap items-center gap-2">
            {event.registration_required && !cancelled && !past && (
              <SelfRegistration
                eventId={event.id}
                isRegistered={event.is_registered}
              />
            )}
            {canManage && (
              <>
                <EventDialog event={event} />
                {!cancelled && (
                  <ConfirmAction
                    trigger={
                      <Button variant="outline" size="sm">
                        <BanIcon />
                        {t("detail.cancel")}
                      </Button>
                    }
                    title={t("cancelDialog.title")}
                    description={t("cancelDialog.description")}
                    confirmLabel={t("cancelDialog.confirm")}
                    successMessage={t("toasts.cancelled")}
                    action={cancelEventAction.bind(null, event.id)}
                  />
                )}
                <ConfirmAction
                  trigger={
                    <Button variant="ghost" size="sm" aria-label={t("detail.delete")}>
                      <Trash2Icon className="text-destructive" />
                    </Button>
                  }
                  title={t("deleteDialog.title")}
                  description={t("deleteDialog.description", {
                    count: event.registered_count,
                  })}
                  confirmLabel={t("deleteDialog.confirm")}
                  successMessage={t("toasts.deleted")}
                  redirectTo="/events"
                  action={deleteEventAction.bind(null, event.id)}
                />
              </>
            )}
          </div>
        </div>
      </div>

      {cancelled && (
        <Alert variant="destructive">
          <BanIcon />
          <AlertTitle>{t("cancelledAlert.title")}</AlertTitle>
          <AlertDescription>
            {t("cancelledAlert.description")}
          </AlertDescription>
        </Alert>
      )}

      <dl className="grid gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-4">
        <Fact
          label={t("columns.date")}
          value={formatDate(event.starts_at, locale, timeZone)}
        />
        <Fact label={t("columns.time")}>
          {event.all_day ? (
            t("allDay")
          ) : (
            <span className="tabular-nums">
              {formatTime(event.starts_at, locale, timeZone)}
              {event.ends_at &&
                `–${formatTime(event.ends_at, locale, timeZone)}`}
            </span>
          )}
        </Fact>
        <Fact label={t("columns.location")} value={event.location} />
        <Fact label={t("fields.registration")}>
          {event.registration_required
            ? event.max_participants
              ? t("detail.seats", {
                  count: event.registered_count,
                  max: event.max_participants,
                })
              : t("detail.registeredCount", { count: event.registered_count })
            : t("detail.noRegistration")}
        </Fact>
        {event.registration_required && event.registration_deadline && (
          <Fact
            label={t("fields.deadline")}
            value={formatDateTime(
              event.registration_deadline,
              locale,
              timeZone
            )}
          />
        )}
        {event.description && (
          <div className="space-y-1 sm:col-span-2 lg:col-span-4">
            <dt className="text-xs text-muted-foreground">
              {t("fields.description")}
            </dt>
            <dd className="text-sm whitespace-pre-line">{event.description}</dd>
          </div>
        )}
      </dl>

      {event.registration_required && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">
            {t("registrations.title", { count: event.registered_count })}
          </h2>
          <RegistrationsPanel
            eventId={event.id}
            registrations={event.registrations}
            timeZone={timeZone}
            canManage={canManage}
          />
        </section>
      )}

      {/* Board only — the backend sends no sessions to anyone else. */}
      {canManage && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">
            {t("attendance.title")}
          </h2>
          <AttendancePanel
            eventId={event.id}
            sessions={event.attendance_sessions}
            timeZone={timeZone}
            canStart={!cancelled}
          />
        </section>
      )}
    </>
  )
}
