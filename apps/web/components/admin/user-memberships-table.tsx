"use client"

import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import { roleLabel } from "@/lib/labels"
import type { AdminMembership } from "@/lib/types/admin"

export function UserMembershipsTable({
  memberships,
}: {
  memberships: AdminMembership[]
}) {
  const t = useTranslations("admin.userDetail")
  const tl = useTranslations("admin")
  const locale = useLocale()
  const router = useRouter()

  const columns: DataTableColumn<AdminMembership>[] = [
    {
      key: "club",
      header: t("columns.club"),
      sortValue: (row) => row.tenant_name,
      cell: (row) => <span className="font-medium">{row.tenant_name}</span>,
    },
    {
      key: "role",
      header: t("columns.role"),
      sortValue: (row) => roleLabel(tl, row.role),
      cell: (row) => <Badge variant="outline">{roleLabel(tl, row.role)}</Badge>,
    },
    {
      key: "status",
      header: t("columns.status"),
      sortValue: (row) => row.is_active,
      cell: (row) => (
        <Badge variant={row.is_active ? "secondary" : "outline"}>
          {row.is_active ? t("active") : t("inactive")}
        </Badge>
      ),
    },
  ]

  return (
    <DataTable
      data={memberships}
      columns={columns}
      rowKey={(row) => row.tenant_id}
      locale={locale}
      defaultSort={{ key: "club", direction: "asc" }}
      onRowClick={(row) => router.push(`/admin/tenants/${row.tenant_id}`)}
      emptyText={t("noClubs")}
    />
  )
}
