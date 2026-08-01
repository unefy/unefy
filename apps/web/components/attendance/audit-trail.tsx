"use client"

import { useLocale, useTranslations } from "next-intl"

import { formatDateTime } from "@/lib/time"
import type { AuditEntry } from "@/lib/types/attendance"

/**
 * The trail of an evening, oldest first.
 *
 * Shown on the page rather than hidden behind a menu: the record answers who
 * was there, this answers how anyone knows — and that second question is the
 * one that gets asked when it matters. Entries for records that were corrected
 * away are included; those are the ones people go looking for.
 */
export function AuditTrail({
  entries,
  timeZone,
}: {
  entries: AuditEntry[]
  /** The club's zone — see `lib/time`. */
  timeZone: string
}) {
  const t = useTranslations("attendance.audit")
  const locale = useLocale()

  if (entries.length === 0) {
    return (
      <p className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
        {t("empty")}
      </p>
    )
  }

  const stamp = (value: string) => formatDateTime(value, locale, timeZone)

  return (
    <ol className="divide-y rounded-md border">
      {entries.map((entry) => (
        <li key={entry.id} className="space-y-1 px-4 py-3">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <span className="text-sm font-medium">
              {t(`actions.${entry.action}`)}
            </span>
            <span className="text-xs text-muted-foreground">
              {t("by", { name: entry.actor_name ?? t("system") })} ·{" "}
              {stamp(entry.created_at)}
            </span>
          </div>
          {entry.reason && (
            <p className="text-sm text-muted-foreground">
              {t("reason")}: {entry.reason}
            </p>
          )}
        </li>
      ))}
    </ol>
  )
}
