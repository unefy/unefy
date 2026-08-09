import { getTranslations } from "next-intl/server"

import { CompetitionDialog } from "@/components/competitions/competition-dialog"
import { CompetitionsTable } from "@/components/competitions/competitions-table"
import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"
import { getClubTimeZone } from "@/lib/attendance"
import { getSession } from "@/lib/auth"
import { listCompetitions } from "@/lib/competitions"
import { listClubDisciplines } from "@/lib/catalog"

const BOARD_ROLES = ["owner", "admin", "board"]

export default async function CompetitionsPage() {
  const [t, timeZone, session] = await Promise.all([
    getTranslations("competitions"),
    getClubTimeZone(),
    getSession(),
  ])

  const [competitions, disciplines] = await Promise.all([
    listCompetitions().catch(() => ({ data: [], meta: { total: 0 } })),
    // Only used to suggest names in the form — a club without a catalogue
    // still types its own.
    listClubDisciplines().catch(() => []),
  ])

  const canManage = BOARD_ROLES.includes(session?.role ?? "")

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <HeaderScrollTitle title={t("title")} />
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("title")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("description", { count: competitions.meta.total })}
          </p>
        </div>
        {canManage && (
          <CompetitionDialog
            suggestions={disciplines.map((discipline) => discipline.name)}
          />
        )}
      </div>

      <CompetitionsTable
        competitions={competitions.data}
        timeZone={timeZone}
      />
    </>
  )
}
