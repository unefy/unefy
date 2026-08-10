import { getTranslations } from "next-intl/server"

import { EventsTable } from "@/components/events/events-table"
import { getClubTimeZone } from "@/lib/attendance"
import { listEvents } from "@/lib/events"

/**
 * The events this member is on.
 *
 * Filtered from the ordinary list rather than through an endpoint of its own:
 * every event already carries `is_registered` for the caller, so a second
 * route would be a second source of the same truth.
 */
export default async function MyEventsPage() {
  const [t, { data }, timeZone] = await Promise.all([
    getTranslations("my.events"),
    listEvents().catch(() => ({ data: [], meta: { total: 0 } })),
    getClubTimeZone(),
  ])

  const mine = data.filter((event) => event.is_registered)

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium text-muted-foreground">
        {t("heading", { count: mine.length })}
      </h2>
      <EventsTable events={mine} timeZone={timeZone} now={new Date().getTime()} />
    </section>
  )
}
