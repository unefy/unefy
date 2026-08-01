import Link from "next/link"
import { notFound } from "next/navigation"
import { getLocale, getTranslations } from "next-intl/server"

import { AttendanceList } from "@/components/attendance/attendance-list"
import { AuditTrail } from "@/components/attendance/audit-trail"
import { CloseSessionDialog } from "@/components/attendance/close-session-dialog"
import { ReasonDialog } from "@/components/attendance/reason-dialog"
import { SessionDialog } from "@/components/attendance/session-dialog"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  getAttendanceSession,
  getAttendanceSessionAudit,
  getClubTimeZone,
} from "@/lib/attendance"
import { formatDate, formatTime } from "@/lib/time"
import { deleteSessionAction } from "@/actions/attendance"
import { ArrowLeftIcon, LockIcon, Trash2Icon } from "lucide-react"

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

export default async function AttendanceSessionPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const [t, locale, timeZone, { id }] = await Promise.all([
    getTranslations("attendance"),
    getLocale(),
    getClubTimeZone(),
    params,
  ])

  const session = await getAttendanceSession(id).catch(() => null)
  if (!session) notFound()

  const audit = await getAttendanceSessionAudit(id).catch(() => [])

  const closed = session.status === "closed"

  return (
    <>
      <div className="space-y-3">
        <Link
          href="/attendance"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeftIcon className="size-4" />
          {t("detail.back")}
        </Link>

        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">
            {session.title}
          </h1>
          {closed ? (
            <Badge variant="secondary" className="gap-1">
              <LockIcon className="size-3" />
              {t("status.closed")}
            </Badge>
          ) : (
            <Badge variant="outline">{t("status.open")}</Badge>
          )}

          <div className="ms-auto flex flex-wrap items-center gap-2">
            {!closed && (
              <>
                <SessionDialog session={session} />
                <CloseSessionDialog
                  sessionId={session.id}
                  recordCount={session.record_count}
                />
                {session.record_count === 0 && (
                  <ReasonDialog
                    trigger={
                      <Button variant="ghost" size="sm">
                        <Trash2Icon className="text-destructive" />
                      </Button>
                    }
                    title={t("deleteDialog.title")}
                    description={t("deleteDialog.description")}
                    confirmLabel={t("deleteDialog.confirm")}
                    successMessage={t("toasts.sessionDeleted")}
                    // Bound rather than wrapped in an arrow: a plain closure
                    // is not a server action and cannot cross into a client
                    // component.
                    action={deleteSessionAction.bind(null, session.id)}
                  />
                )}
              </>
            )}
          </div>
        </div>
      </div>

      <dl className="grid gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-4">
        <Fact
          label={t("columns.date")}
          value={formatDate(session.opens_at, locale, timeZone)}
        />
        <Fact label={t("columns.time")}>
          <span className="tabular-nums">
            {formatTime(session.opens_at, locale, timeZone)}–
            {formatTime(session.closes_at, locale, timeZone)}
          </span>
        </Fact>
        <Fact label={t("columns.location")} value={session.location} />
        <Fact label={t("columns.supervisor")} value={session.supervisor_name} />
      </dl>

      {closed && (
        <Alert>
          <LockIcon />
          <AlertTitle>{t("frozen.title")}</AlertTitle>
          <AlertDescription>
            {t("frozen.description", { count: session.record_count })}
          </AlertDescription>
        </Alert>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">
          {t("detail.present", { count: session.record_count })}
        </h2>
        <AttendanceList session={session} timeZone={timeZone} />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">
          {t("detail.trail")}
        </h2>
        <AuditTrail entries={audit} timeZone={timeZone} />
      </section>
    </>
  )
}
