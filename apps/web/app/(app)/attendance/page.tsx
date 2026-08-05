import { getTranslations } from "next-intl/server"
import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"

import { SessionDialog } from "@/components/attendance/session-dialog"
import { SessionsTable } from "@/components/attendance/sessions-table"
import { getClubTimeZone, listAttendanceSessions } from "@/lib/attendance"

export default async function AttendancePage() {
  const [t, { data, meta }, timeZone] = await Promise.all([
    getTranslations("attendance"),
    listAttendanceSessions(),
    getClubTimeZone(),
  ])

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
        <SessionDialog />
      </div>
      <SessionsTable sessions={data} timeZone={timeZone} />
    </>
  )
}
