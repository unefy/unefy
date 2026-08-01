import { getTranslations } from "next-intl/server"

import { PageHeader } from "@/components/admin/page-header"
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { listAuditLog, listTenants, listUsers } from "@/lib/admin"

export default async function AdminOverviewPage() {
  const t = await getTranslations("admin.overview")

  // Only the envelope totals are needed, so ask for the smallest page the API
  // allows rather than pulling full result sets just to count them.
  const [tenants, users, audit] = await Promise.all([
    listTenants(),
    listUsers(),
    listAuditLog(),
  ])

  const stats = [
    { key: "clubs", value: tenants.meta.total },
    { key: "users", value: users.meta.total },
    { key: "auditEntries", value: audit.meta.total },
  ]

  return (
    <>
      <PageHeader title={t("title")} description={t("description")} />

      <div className="grid gap-4 @2xl/content:grid-cols-3">
        {stats.map((stat) => (
          <Card key={stat.key}>
            <CardHeader>
              <CardDescription>{t(`stats.${stat.key}`)}</CardDescription>
              <CardTitle className="text-3xl tabular-nums">
                {stat.value}
              </CardTitle>
            </CardHeader>
          </Card>
        ))}
      </div>
    </>
  )
}
