"use client"

import { useTranslations } from "next-intl"
import { MembersTable } from "@/components/members/members-table"
import { MemberCreateDialog } from "@/components/members/member-create-dialog"
import { PageHeader } from "@/components/layout/page-header"

export function MembersView() {
  const t = useTranslations("members")

  return (
    <div className="space-y-6">
      <PageHeader title={t("title")} description={t("description")}>
        <MemberCreateDialog />
      </PageHeader>
      <MembersTable />
    </div>
  )
}
