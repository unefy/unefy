import { getTranslations } from "next-intl/server"
import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"

import { ClubSportsForm } from "@/components/settings/club-sports-form"
import { getSession } from "@/lib/auth"
import { getClub } from "@/lib/club"
import { listAvailableSports } from "@/lib/sports"

/** Writing the sports set is restricted to these roles in the backend. */
const EDITOR_ROLES = ["owner", "admin"]

export default async function ClubSportsPage() {
  const [t, club, catalog, session] = await Promise.all([
    getTranslations("clubSettings.sports"),
    getClub(),
    listAvailableSports(),
    getSession(),
  ])

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
      <ClubSportsForm
        catalog={catalog}
        active={club.sports}
        canEdit={canEdit}
      />
    </>
  )
}
