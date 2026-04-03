import { useTranslations } from "next-intl"
import { PageHeader } from "@/components/layout/page-header"

export default function DashboardPage() {
  const t = useTranslations("dashboard")

  return (
    <div className="space-y-8">
      <PageHeader title={t("title")} description={t("description")} />
    </div>
  )
}
