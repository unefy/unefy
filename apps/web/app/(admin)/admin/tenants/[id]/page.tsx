import { notFound } from "next/navigation"
import { getTranslations } from "next-intl/server"

import { PageHeader } from "@/components/admin/page-header"
import { TenantMembersTable } from "@/components/admin/tenant-members-table"
import { TenantUsersTable } from "@/components/admin/tenant-users-table"
import { Badge } from "@/components/ui/badge"
import { DateCell } from "@/components/ui/date-cell"
import { getTenant, listTenantMembers, listTenantUsers } from "@/lib/admin"

function Fact({
  label,
  value,
  children,
}: {
  label: string
  value?: string | null
  children?: React.ReactNode
}) {
  return (
    <div className="space-y-1">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm">{children ?? (value?.trim() ? value : "—")}</dd>
    </div>
  )
}

export default async function AdminTenantDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const [t, { id }] = await Promise.all([
    getTranslations("admin.tenantDetail"),
    params,
  ])

  const tenant = await getTenant(id).catch(() => null)
  if (!tenant) notFound()

  const [users, members] = await Promise.all([
    listTenantUsers(id),
    listTenantMembers(id),
  ])

  const address = [
    tenant.street,
    [tenant.zip_code, tenant.city].filter(Boolean).join(" "),
    tenant.country,
  ]
    .filter((part) => part?.trim())
    .join(", ")

  return (
    <>
      <PageHeader title={tenant.name} description={tenant.slug}>
        <Badge variant={tenant.is_active ? "secondary" : "outline"}>
          {tenant.is_active ? t("active") : t("inactive")}
        </Badge>
      </PageHeader>

      <dl className="grid gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-4">
        <Fact label={t("fields.shortName")} value={tenant.short_name} />
        <Fact label={t("fields.address")} value={address || null} />
        <Fact label={t("fields.email")} value={tenant.email} />
        <Fact label={t("fields.phone")} value={tenant.phone} />
        <Fact label={t("fields.website")} value={tenant.website} />
        <Fact label={t("fields.foundedAt")}>
          <DateCell value={tenant.founded_at} dateOnly />
        </Fact>
        <Fact label={t("fields.createdAt")}>
          <DateCell value={tenant.created_at} />
        </Fact>
        <Fact
          label={t("fields.counts")}
          value={t("countsValue", {
            members: tenant.member_count,
            users: tenant.user_count,
          })}
        />
      </dl>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">
          {t("users")}
        </h2>
        <TenantUsersTable users={users} />
      </section>

      <section className="space-y-3">
        <div className="space-y-1">
          <h2 className="text-sm font-medium text-muted-foreground">
            {t("members")}
          </h2>
          <p className="text-xs text-muted-foreground">{t("membersHint")}</p>
        </div>
        <TenantMembersTable members={members} />
      </section>
    </>
  )
}
