import { getTranslations } from "next-intl/server"

import { OwnAttendanceTable } from "@/components/my/own-attendance-table"
import { getClubTimeZone, listOwnAttendance } from "@/lib/attendance"
import { listClubDisciplines } from "@/lib/catalog"
import { getClub } from "@/lib/club"
import { listOwnShootingDetails } from "@/lib/shooting"

/**
 * The member's own range days — the read side of what the club records about
 * them, and of what they keep themselves.
 *
 * Three reads rather than one enriched response, for the same reason the
 * supervisor's list makes three: attendance belongs to the core every club
 * has, the discipline and round count belong to a module most do not.
 */
export default async function MyAttendancePage() {
  const [t, timeZone, club] = await Promise.all([
    getTranslations("my.attendance"),
    getClubTimeZone(),
    getClub().catch(() => null),
  ])

  const showShooting = club?.modules.includes("shooting") ?? false
  const [attendance, details, disciplines] = await Promise.all([
    listOwnAttendance().catch(() => ({
      data: [],
      total: 0,
      truncated: false,
    })),
    showShooting ? listOwnShootingDetails().catch(() => []) : [],
    showShooting ? listClubDisciplines().catch(() => []) : [],
  ])

  const byRecord = Object.fromEntries(
    details.map((detail) => [detail.attendance_record_id, detail])
  )
  const disciplineNames = Object.fromEntries(
    disciplines.map((discipline) => [discipline.id, discipline.name])
  )

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium text-muted-foreground">
        {t("heading", { count: attendance.total })}
      </h2>
      {attendance.truncated && (
        <p className="text-sm text-destructive">
          {t("truncated", { shown: attendance.data.length })}
        </p>
      )}
      <OwnAttendanceTable
        records={attendance.data}
        details={byRecord}
        disciplineNames={disciplineNames}
        timeZone={timeZone}
        showShooting={showShooting}
      />
    </section>
  )
}
