import { getTranslations } from "next-intl/server"
import { PageHeader } from "@/components/layout/page-header"

export default async function DashboardPage() {
  const t = await getTranslations("dashboard")

  return (
    <div className="space-y-8">
      <PageHeader title={t("title")} description={t("description")} />
    </div>
  )
}
