import { getTranslations } from "next-intl/server"

import { DivisionDialog } from "@/components/settings/division-dialog"
import { DivisionsTable } from "@/components/settings/divisions-table"
import { getSession } from "@/lib/auth"
import { getClub } from "@/lib/club"
import { listClubDivisions } from "@/lib/functions"

/** Changing the club's structure is restricted to these roles in the backend. */
const EDITOR_ROLES = ["owner", "admin"]

/**
 * The club's divisions.
 *
 * Until now they could only be created during onboarding — a club that
 * decided to add a section afterwards had no way to say so, while every
 * division picker in the app kept reading the list.
 */
export default async function ClubDivisionsPage() {
  const [t, divisions, club, session] = await Promise.all([
    getTranslations("clubSettings.divisions"),
    listClubDivisions().catch(() => []),
    getClub().catch(() => null),
    getSession(),
  ])

  const canEdit = EDITOR_ROLES.includes(session?.role ?? "")
  const sports = club?.sports ?? []

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            {t("description")}
          </p>
        </div>
        {canEdit && <DivisionDialog sports={sports} />}
      </div>

      <DivisionsTable
        divisions={divisions}
        sports={sports}
        canEdit={canEdit}
      />

      {!canEdit && (
        <p className="text-sm text-muted-foreground">{t("readOnly")}</p>
      )}
    </>
  )
}
