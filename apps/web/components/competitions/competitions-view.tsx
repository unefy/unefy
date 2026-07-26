"use client"

import { useTranslations } from "next-intl"
import { PageHeader } from "@/components/layout/page-header"
import { CompetitionCreateDialog } from "@/components/competitions/competition-create-dialog"
import { CompetitionsTable } from "@/components/competitions/competitions-table"

export function CompetitionsView() {
  const t = useTranslations("competitions")

  return (
    <div className="space-y-6">
      <PageHeader title={t("title")} description={t("description")}>
        <CompetitionCreateDialog />
      </PageHeader>

      <CompetitionsTable />
    </div>
  )
}
