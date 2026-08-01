import { getTranslations } from "next-intl/server"

import { PageHeader } from "@/components/admin/page-header"
import { UsersTable } from "@/components/admin/users-table"
import { ADMIN_PAGE_SIZE, listUsers } from "@/lib/admin"

export default async function AdminUsersPage() {
  const [t, { data, meta }] = await Promise.all([
    getTranslations("admin.users"),
    listUsers({ perPage: ADMIN_PAGE_SIZE }),
  ])

  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description", { count: meta.total })}
      />
      <UsersTable users={data} />
    </>
  )
}
