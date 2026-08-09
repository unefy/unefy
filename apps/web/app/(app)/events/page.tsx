import { getTranslations } from "next-intl/server"

import { EventDialog } from "@/components/events/event-dialog"
import { EventsTable } from "@/components/events/events-table"
import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"
import { getClubTimeZone } from "@/lib/attendance"
import { getSession } from "@/lib/auth"
import { listEvents } from "@/lib/events"

const BOARD_ROLES = ["owner", "admin", "board"]

export default async function EventsPage() {
  const [t, { data, meta }, timeZone, session] = await Promise.all([
    getTranslations("events"),
    listEvents(),
    getClubTimeZone(),
    getSession(),
  ])

  const canManage = BOARD_ROLES.includes(session?.role ?? "")
  const now = new Date().getTime()

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <HeaderScrollTitle title={t("title")} />
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("title")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("description", { count: meta.total })}
          </p>
        </div>
        {canManage && <EventDialog />}
      </div>
      {/*
        `now` is stamped on the server and handed down, so the "upcoming"
        filter means the same thing in the server-rendered HTML and after
        hydration.
      */}
      <EventsTable events={data} timeZone={timeZone} now={now} />
    </>
  )
}
