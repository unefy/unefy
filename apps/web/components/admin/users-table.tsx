"use client"

import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import { DateCell } from "@/components/ui/date-cell"
import type { AdminUser } from "@/lib/types/admin"

export function UsersTable({ users }: { users: AdminUser[] }) {
  const t = useTranslations("admin.users")
  const locale = useLocale()
  const router = useRouter()

  const columns: DataTableColumn<AdminUser>[] = [
    {
      key: "name",
      header: t("columns.name"),
      sortValue: (row) => row.name,
      cell: (row) => <span className="font-medium">{row.name}</span>,
    },
    {
      key: "email",
      header: t("columns.email"),
      sortValue: (row) => row.email,
      cellClassName: "text-muted-foreground",
      cell: (row) => row.email,
    },
    {
      key: "role",
      header: t("columns.role"),
      sortValue: (row) => row.is_superuser,
      cell: (row) =>
        row.is_superuser ? (
          <Badge variant="destructive">{t("platformAdmin")}</Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      key: "createdAt",
      header: t("columns.createdAt"),
      sortValue: (row) => row.created_at,
      cellClassName: "text-muted-foreground",
      cell: (row) => <DateCell value={row.created_at} />,
    },
  ]

  return (
    <DataTable
      data={users}
      columns={columns}
      rowKey={(row) => row.id}
      locale={locale}
      defaultSort={{ key: "name", direction: "asc" }}
      searchPlaceholder={t("searchPlaceholder")}
      searchFields={(row) => [row.name, row.email]}
      filters={[
        {
          key: "role",
          allLabel: t("filters.allRoles"),
          options: [
            { value: "admin", label: t("platformAdmin") },
            { value: "user", label: t("filters.regularUser") },
          ],
          matches: (row, value) => row.is_superuser === (value === "admin"),
        },
      ]}
      onRowClick={(row) => router.push(`/admin/users/${row.id}`)}
      emptyText={t("empty")}
    />
  )
}
