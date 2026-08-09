"use client"

import { useTransition } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { toast } from "sonner"

import { startAttendanceAction } from "@/actions/events"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { formatDate, formatTime } from "@/lib/time"
import type { AttendanceSession } from "@/lib/types/attendance"
import { ClipboardCheckIcon, LockIcon, PlayIcon } from "lucide-react"

/**
 * The event's second door into attendance.
 *
 * Whoever opens the training evening in the calendar steps through to who was
 * there — the list is otherwise only reachable behind the scanner.
 */
export function AttendancePanel({
  eventId,
  sessions,
  timeZone,
  canStart,
}: {
  eventId: string
  sessions: AttendanceSession[]
  timeZone: string
  /** Board roles on an event that is neither cancelled nor long past. */
  canStart: boolean
}) {
  const t = useTranslations("events.attendance")
  const locale = useLocale()
  const router = useRouter()
  const [pending, startTransition] = useTransition()

  const hasOpen = sessions.some((session) => session.status === "open")

  function start() {
    startTransition(async () => {
      const result = await startAttendanceAction(eventId)
      if (result.success && result.data) {
        toast.success(t("startedToast"))
        // Straight into the list — starting attendance is never the goal, it is
        // the step before checking people in.
        router.push(`/attendance/${result.data.id}`)
      } else if (!result.success) {
        toast.error(t(`errors.${result.error}`))
      }
    })
  }

  return (
    <div className="space-y-3">
      {sessions.length === 0 ? (
        <div className="rounded-md border p-4 text-sm text-muted-foreground">
          {t("none")}
        </div>
      ) : (
        <div className="divide-y rounded-md border">
          {sessions.map((session) => (
            <Link
              key={session.id}
              href={`/attendance/${session.id}`}
              className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm hover:bg-muted/50"
            >
              <div className="space-y-0.5">
                <div className="font-medium">{session.title}</div>
                <div className="text-xs text-muted-foreground tabular-nums">
                  {formatDate(session.opens_at, locale, timeZone)} ·{" "}
                  {formatTime(session.opens_at, locale, timeZone)}–
                  {formatTime(session.closes_at, locale, timeZone)}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="gap-1">
                  <ClipboardCheckIcon className="size-3" />
                  {t("records", { count: session.record_count })}
                </Badge>
                {session.status === "closed" && (
                  <Badge variant="outline" className="gap-1">
                    <LockIcon className="size-3" />
                    {t("closed")}
                  </Badge>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}

      {canStart && !hasOpen && (
        <Button size="sm" disabled={pending} onClick={start}>
          <PlayIcon />
          {pending ? t("starting") : t("start")}
        </Button>
      )}
    </div>
  )
}
