import { getTranslations } from "next-intl/server"
import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"

import { MemberDialog } from "@/components/members/member-dialog"
import { MembersTable } from "@/components/members/members-table"
import { listAllMembers } from "@/lib/members"

export default async function MembersPage() {
  const [t, { data, total, truncated }] = await Promise.all([
    getTranslations("members"),
    listAllMembers(),
  ])

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <HeaderScrollTitle title={t("title")} />
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("title")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("description", { count: total })}
          </p>
        </div>
        <MemberDialog />
      </div>
      {truncated && (
        <p className="text-sm text-destructive">{t("truncated", { shown: data.length })}</p>
      )}
      <MembersTable members={data} />
    </>
  )
}
