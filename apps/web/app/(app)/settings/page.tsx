import { getTranslations } from "next-intl/server"
import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"

import { ClubGeneralForm } from "@/components/settings/club-general-form"
import { getSession } from "@/lib/auth"
import { getClub } from "@/lib/club"

/** Writing the club record is restricted to these roles in the backend. */
const EDITOR_ROLES = ["owner", "admin"]

export default async function ClubSettingsPage() {
  const [t, club, session] = await Promise.all([
    getTranslations("clubSettings"),
    getClub(),
    getSession(),
  ])

  // A board member may read the club record but not change it. Showing the
  // form disabled beats hiding the page: the answer to "what is our time zone"
  // should not depend on holding the right role.
  const canEdit = EDITOR_ROLES.includes(session?.role ?? "")

  return (
    <>
      <div className="space-y-1">
        <HeaderScrollTitle title={t("title")} />
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          {t("description")}
        </p>
      </div>
      <ClubGeneralForm club={club} canEdit={canEdit} />
    </>
  )
}
