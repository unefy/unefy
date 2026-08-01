import { getTranslations } from "next-intl/server"

import { MemberDialog } from "@/components/members/member-dialog"
import { MembersTable } from "@/components/members/members-table"
import { MEMBER_PAGE_SIZE, listMembers } from "@/lib/members"

export default async function MembersPage() {
  const [t, { data, meta }] = await Promise.all([
    getTranslations("members"),
    listMembers({ perPage: MEMBER_PAGE_SIZE }),
  ])

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("title")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("description", { count: meta.total })}
          </p>
        </div>
        <MemberDialog />
      </div>
      <MembersTable members={data} />
    </>
  )
}
