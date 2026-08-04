import { notFound } from "next/navigation"
import { getTranslations } from "next-intl/server"

import { RuleDialog } from "@/components/shooting/rule-dialog"
import { RulesTable } from "@/components/shooting/rules-table"
import { getClub } from "@/lib/club"
import { getSession } from "@/lib/auth"
import { listShootingRules } from "@/lib/shooting"

/** Only owner/admin may change rules — board reads them (settings pattern:
 * show read-only rather than hide). */
const EDITOR_ROLES = ["owner", "admin"]

export default async function ShootingRulesPage() {
  const club = await getClub().catch(() => null)
  if (!club?.modules.includes("shooting")) notFound()

  const [t, session, rules] = await Promise.all([
    getTranslations("shooting.rules"),
    getSession(),
    listShootingRules().catch(() => null),
  ])
  if (rules === null) notFound()

  const canEdit = EDITOR_ROLES.includes(session?.role ?? "")

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("title")}
          </h1>
          <p className="text-sm text-muted-foreground">{t("description")}</p>
        </div>
        {canEdit && <RuleDialog />}
      </div>
      <RulesTable rules={rules} canEdit={canEdit} />
    </>
  )
}
