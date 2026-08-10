import { getTranslations } from "next-intl/server"

import { Badge } from "@/components/ui/badge"
import type { AttendanceRecord } from "@/lib/types/attendance"
import type { EventRegistration } from "@/lib/types/event"
import { UserCheckIcon, UserMinusIcon, UserPlusIcon } from "lucide-react"

/**
 * Who said they would come, and who did.
 *
 * A read of two lists that already exist, never a third record: the RSVP is a
 * promise and the attendance is evidence, and nothing here writes either.
 * Which is also why a mismatch is stated rather than resolved — somebody who
 * registered and did not appear may have been ticked off on paper, and this
 * screen has no business deciding that.
 */
export async function RsvpMirror({
  registrations,
  records,
}: {
  registrations: EventRegistration[]
  /** Every record of every attendance session hung off this event. */
  records: AttendanceRecord[]
}) {
  const t = await getTranslations("events.mirror")

  // Waitlisted people never had a seat, so their absence says nothing. Guests
  // carry no member id and cannot be matched against a registration at all.
  const promised = new Map(
    registrations
      .filter((registration) => registration.status === "registered")
      .map((registration) => [registration.member_id, registration])
  )
  const present = new Map<string, AttendanceRecord>()
  for (const record of records) {
    if (record.member_id) present.set(record.member_id, record)
  }

  const kept = [...promised.keys()].filter((id) => present.has(id))
  const noShows = [...promised.values()].filter(
    (registration) => !present.has(registration.member_id)
  )
  const walkIns = [...present.keys()].filter((id) => !promised.has(id))
  const guests = records.filter((record) => record.member_id === null).length

  const nameOf = (memberId: string) =>
    promised.get(memberId)?.member_name ??
    present.get(memberId)?.member_name ??
    "—"

  return (
    <div className="space-y-4 rounded-md border p-4">
      <div className="flex flex-wrap items-center gap-4 text-sm">
        <span className="flex items-center gap-1.5">
          <UserCheckIcon className="size-4 text-muted-foreground" />
          {t("kept", { count: kept.length })}
        </span>
        <span className="flex items-center gap-1.5">
          <UserMinusIcon className="size-4 text-muted-foreground" />
          {t("noShows", { count: noShows.length })}
        </span>
        <span className="flex items-center gap-1.5">
          <UserPlusIcon className="size-4 text-muted-foreground" />
          {t("walkIns", { count: walkIns.length })}
        </span>
        {guests > 0 && (
          <span className="text-muted-foreground">
            {t("guests", { count: guests })}
          </span>
        )}
      </div>

      {noShows.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">{t("noShowsTitle")}</p>
          <div className="flex flex-wrap gap-1.5">
            {noShows.map((registration) => (
              <Badge key={registration.id} variant="outline">
                {registration.member_name ?? "—"}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {walkIns.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">{t("walkInsTitle")}</p>
          <div className="flex flex-wrap gap-1.5">
            {walkIns.map((memberId) => (
              <Badge key={memberId} variant="secondary">
                {nameOf(memberId)}
              </Badge>
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-muted-foreground">{t("hint")}</p>
    </div>
  )
}
