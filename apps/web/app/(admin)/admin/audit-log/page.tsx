import { getTranslations } from "next-intl/server"

import { AuditLogTable } from "@/components/admin/audit-log-table"
import { PageHeader } from "@/components/admin/page-header"
import { ADMIN_PAGE_SIZE, listAuditLog } from "@/lib/admin"

export default async function AdminAuditLogPage() {
  const [t, { data, meta }] = await Promise.all([
    getTranslations("admin.auditLog"),
    listAuditLog({ perPage: ADMIN_PAGE_SIZE }),
  ])

  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description", { count: meta.total })}
      />
      <AuditLogTable entries={data} />
    </>
  )
}
