import { getTranslations } from "next-intl/server"

import { ClubAccessTables } from "@/components/settings/club-access-tables"
import { getClubAccess } from "@/lib/members"

export default async function ClubAccessPage() {
  const [t, access] = await Promise.all([
    getTranslations("clubAccess"),
    getClubAccess(),
  ])

  return (
    <>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          {t("description")}
        </p>
      </div>
      <ClubAccessTables access={access} />
    </>
  )
}
