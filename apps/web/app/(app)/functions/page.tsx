import { getTranslations } from "next-intl/server"

import { FunctionHolders } from "@/components/members/function-holders"
import { getClub } from "@/lib/club"
import { listFunctionHolders } from "@/lib/functions"

/** The board list — readable by every member; writes happen on the member
 * detail's functions tab. */
export default async function FunctionHoldersPage({
  searchParams,
}: {
  searchParams: Promise<{ at?: string }>
}) {
  const [t, { at }] = await Promise.all([
    getTranslations("functionHolders"),
    searchParams,
  ])

  const effectiveAt =
    at && /^\d{4}-\d{2}-\d{2}$/.test(at)
      ? at
      : new Date().toISOString().slice(0, 10)

  const [holders, club] = await Promise.all([
    listFunctionHolders(effectiveAt).catch(() => []),
    getClub().catch(() => null),
  ])

  return (
    <>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          {t("description")}
        </p>
      </div>
      <FunctionHolders
        holders={holders}
        at={effectiveAt}
        hasDivisions={club?.has_divisions ?? false}
      />
    </>
  )
}
