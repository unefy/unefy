"use client"

import { useSearchParams } from "next/navigation"
import { useTranslations } from "next-intl"
import { PageHeader } from "@/components/layout/page-header"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { DuesSummaryCards } from "@/components/dues/dues-summary-cards"
import { DuesTable } from "@/components/dues/dues-table"
import { FeeTypesTable } from "@/components/dues/fee-types-table"
import { GenerateDuesDialog } from "@/components/dues/generate-dues-dialog"
import { SepaExportButton } from "@/components/dues/sepa-export-button"

export function DuesView() {
  const t = useTranslations("dues")
  const searchParams = useSearchParams()
  const year = Number(searchParams.get("year")) || new Date().getFullYear()

  return (
    <div className="space-y-6">
      <PageHeader title={t("title")} description={t("description")}>
        <SepaExportButton year={year} />
        <GenerateDuesDialog />
      </PageHeader>

      <DuesSummaryCards year={year} />

      <Tabs defaultValue="dues">
        <TabsList>
          <TabsTrigger value="dues">{t("openItems")}</TabsTrigger>
          <TabsTrigger value="feeTypes">{t("feeTypes")}</TabsTrigger>
        </TabsList>
        <TabsContent value="dues" className="pt-4">
          <DuesTable />
        </TabsContent>
        <TabsContent value="feeTypes" className="pt-4">
          <FeeTypesTable />
        </TabsContent>
      </Tabs>
    </div>
  )
}
