"use client"

import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { useTranslations } from "next-intl"
import { PageHeader } from "@/components/layout/page-header"
import { Button } from "@/components/ui/button"
import { DuesSummaryCards } from "@/components/dues/dues-summary-cards"
import { DuesTable } from "@/components/dues/dues-table"
import { GenerateDuesDialog } from "@/components/dues/generate-dues-dialog"
import { SepaExportButton } from "@/components/dues/sepa-export-button"

export function DuesView() {
  const t = useTranslations("dues")
  const searchParams = useSearchParams()
  const year = Number(searchParams.get("year")) || new Date().getFullYear()

  return (
    <div className="space-y-6">
      <PageHeader title={t("title")} description={t("description")}>
        <Button
          variant="outline"
          nativeButton={false}
          render={<Link href="/settings/fees" />}
        >
          {t("manageFeeTypes")}
        </Button>
        <SepaExportButton year={year} />
        <GenerateDuesDialog />
      </PageHeader>

      <DuesSummaryCards year={year} />

      <DuesTable />
    </div>
  )
}
