import { getTranslations } from "next-intl/server"

import { PageHeader } from "@/components/admin/page-header"
import { TenantsTable } from "@/components/admin/tenants-table"
import { ADMIN_PAGE_SIZE, listTenants } from "@/lib/admin"

export default async function AdminTenantsPage() {
  const [t, { data, meta }] = await Promise.all([
    getTranslations("admin.tenants"),
    listTenants({ perPage: ADMIN_PAGE_SIZE }),
  ])

  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description", { count: meta.total })}
      />
      <TenantsTable tenants={data} />
    </>
  )
}
