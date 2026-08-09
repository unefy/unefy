import Link from "next/link"
import { getTranslations } from "next-intl/server"

import { FeeTypeDialog } from "@/components/dues/fee-type-dialog"
import { FeeTypesTable } from "@/components/dues/fee-types-table"
import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"
import { getSession } from "@/lib/auth"
import { listFeeTypes } from "@/lib/dues"
import { ArrowLeftIcon } from "lucide-react"

const EDITOR_ROLES = ["owner", "admin", "board"]
/** Deleting a fee type is owner/admin in the backend — mirrored here. */
const DELETE_ROLES = ["owner", "admin"]

export default async function FeeTypesPage() {
  const [t, session] = await Promise.all([
    getTranslations("dues.feeTypes"),
    getSession(),
  ])

  // Retired types are listed too — otherwise a club could never bring one back.
  const feeTypes = await listFeeTypes(true).catch(() => [])
  const canEdit = EDITOR_ROLES.includes(session?.role ?? "")

  return (
    <>
      <div className="space-y-3">
        <Link
          href="/dues"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeftIcon className="size-4" />
          {t("back")}
        </Link>

        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <HeaderScrollTitle title={t("title")} />
            <h1 className="text-2xl font-semibold tracking-tight">
              {t("title")}
            </h1>
            <p className="text-sm text-muted-foreground">{t("description")}</p>
          </div>
          {canEdit && <FeeTypeDialog />}
        </div>
      </div>

      <FeeTypesTable
        feeTypes={feeTypes}
        canEdit={canEdit}
        canDelete={DELETE_ROLES.includes(session?.role ?? "")}
      />
    </>
  )
}
