"use client"

import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import { roleLabel } from "@/lib/labels"
import type { AdminTenantUser } from "@/lib/types/admin"

export function TenantUsersTable({ users }: { users: AdminTenantUser[] }) {
  const t = useTranslations("admin.tenantDetail")
  const tl = useTranslations("admin")
  const locale = useLocale()
  const router = useRouter()

  const columns: DataTableColumn<AdminTenantUser>[] = [
    {
      key: "name",
      header: t("userColumns.name"),
      sortValue: (row) => row.name,
      cell: (row) => <span className="font-medium">{row.name}</span>,
    },
    {
      key: "email",
      header: t("userColumns.email"),
      sortValue: (row) => row.email,
      cellClassName: "text-muted-foreground",
      cell: (row) => row.email,
    },
    {
      key: "role",
      header: t("userColumns.role"),
      sortValue: (row) => roleLabel(tl, row.role),
      cell: (row) => <Badge variant="outline">{roleLabel(tl, row.role)}</Badge>,
    },
    {
      key: "status",
      header: t("userColumns.status"),
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
      data={users}
      columns={columns}
      rowKey={(row) => row.user_id}
      locale={locale}
      defaultSort={{ key: "name", direction: "asc" }}
      onRowClick={(row) => router.push(`/admin/users/${row.user_id}`)}
      emptyText={t("noUsers")}
    />
  )
}
