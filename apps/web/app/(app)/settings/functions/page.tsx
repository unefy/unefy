import { getTranslations } from "next-intl/server"

import { FunctionDialog } from "@/components/settings/function-dialog"
import { FunctionsTable } from "@/components/settings/functions-table"
import { getSession } from "@/lib/auth"
import { getClub } from "@/lib/club"
import { listFunctions } from "@/lib/functions"

/** Writing the function list is restricted to these roles in the backend. */
const EDITOR_ROLES = ["owner", "admin"]

export default async function ClubFunctionsPage() {
  const [t, functions, club, session] = await Promise.all([
    getTranslations("clubSettings.functions"),
    listFunctions(),
    getClub(),
    getSession(),
  ])

  const canEdit = EDITOR_ROLES.includes(session?.role ?? "")

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("title")}
          </h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            {t("description")}
          </p>
        </div>
        {canEdit && <FunctionDialog hasDivisions={club.has_divisions} />}
      </div>
      <FunctionsTable
        functions={functions}
        hasDivisions={club.has_divisions}
        canEdit={canEdit}
      />
    </>
  )
}
