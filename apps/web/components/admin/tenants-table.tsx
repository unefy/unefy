"use client"

import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import { DateCell } from "@/components/ui/date-cell"
import type { AdminTenant } from "@/lib/types/admin"

export function TenantsTable({ tenants }: { tenants: AdminTenant[] }) {
  const t = useTranslations("admin.tenants")
  const locale = useLocale()
  const router = useRouter()

  const columns: DataTableColumn<AdminTenant>[] = [
    {
      key: "name",
      header: t("columns.name"),
      sortValue: (row) => row.name,
      cell: (row) => (
        <>
          <div className="font-medium">{row.name}</div>
          <div className="text-xs text-muted-foreground">{row.slug}</div>
        </>
      ),
    },
    {
      key: "city",
      header: t("columns.city"),
      sortValue: (row) => row.city,
      cell: (row) => row.city ?? "—",
    },
    {
      key: "memberCount",
      header: t("columns.memberCount"),
      align: "center",
      shrink: true,
      sortValue: (row) => row.member_count,
      cellClassName: "tabular-nums",
      cell: (row) => row.member_count,
    },
    {
      key: "userCount",
      header: t("columns.userCount"),
      align: "center",
      shrink: true,
      sortValue: (row) => row.user_count,
      cellClassName: "tabular-nums",
      cell: (row) => row.user_count,
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
      data={tenants}
      columns={columns}
      rowKey={(row) => row.id}
      locale={locale}
      defaultSort={{ key: "name", direction: "asc" }}
      searchPlaceholder={t("searchPlaceholder")}
      searchFields={(row) => [row.name, row.slug, row.city]}
      filters={[
        {
          key: "status",
          allLabel: t("filters.allStatuses"),
          options: [
            { value: "active", label: t("active") },
            { value: "inactive", label: t("inactive") },
          ],
          matches: (row, value) => row.is_active === (value === "active"),
        },
      ]}
      onRowClick={(row) => router.push(`/admin/tenants/${row.id}`)}
      emptyText={t("empty")}
    />
  )
}
