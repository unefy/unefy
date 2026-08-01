import { notFound } from "next/navigation"
import { getTranslations } from "next-intl/server"

import { ImpersonateDialog } from "@/components/admin/impersonate-dialog"
import { PageHeader } from "@/components/admin/page-header"
import { UserMembershipsTable } from "@/components/admin/user-memberships-table"
import { Badge } from "@/components/ui/badge"
import { getUser, listUserMemberships } from "@/lib/admin"

export default async function AdminUserDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const [t, { id }] = await Promise.all([
    getTranslations("admin.userDetail"),
    params,
  ])

  const [user, memberships] = await Promise.all([
    getUser(id).catch(() => null),
    listUserMemberships(id),
  ])
  if (!user) notFound()

  const hasActiveClub = memberships.some((m) => m.is_active)

  return (
    <>
      <PageHeader title={user.name} description={user.email}>
        {/* Impersonating another platform admin is refused by the backend, so
            the control is not offered here either. */}
        {!user.is_superuser && hasActiveClub && (
          <ImpersonateDialog
            userId={user.id}
            userName={user.name}
            userEmail={user.email}
            memberships={memberships}
          />
        )}
      </PageHeader>

      {user.is_superuser && (
        <Badge variant="destructive" className="w-fit">
          {t("platformAdmin")}
        </Badge>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">
          {t("clubs")}
        </h2>
        <UserMembershipsTable memberships={memberships} />
      </section>
    </>
  )
}
