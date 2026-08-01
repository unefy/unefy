"use client"

import { useMemo } from "react"
import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import { DateCell } from "@/components/ui/date-cell"
import { memberStatusLabel } from "@/lib/labels"
import type { AdminTenantMember } from "@/lib/types/admin"

export function TenantMembersTable({
  members,
}: {
  members: AdminTenantMember[]
}) {
  const t = useTranslations("admin.tenantDetail")
  const tl = useTranslations("admin")
  const locale = useLocale()

  // Statuses are club-defined, so the filter offers what actually occurs
  // rather than a hard-coded list.
  const statuses = useMemo(
    () => [...new Set(members.map((m) => m.status))].sort(),
    [members]
  )

  const columns: DataTableColumn<AdminTenantMember>[] = [
    {
      key: "name",
      header: t("memberColumns.name"),
      sortValue: (row) => `${row.last_name} ${row.first_name}`,
      cell: (row) => (
        <span className="font-medium">
          {row.last_name}, {row.first_name}
        </span>
      ),
    },
    {
      key: "memberNumber",
      header: t("memberColumns.memberNumber"),
      sortValue: (row) => row.member_number,
      cellClassName: "font-mono text-xs text-muted-foreground",
      cell: (row) => row.member_number,
    },
    {
      key: "status",
      header: t("memberColumns.status"),
      sortValue: (row) => memberStatusLabel(tl, row.status),
      cell: (row) => (
        <Badge variant="secondary">{memberStatusLabel(tl, row.status)}</Badge>
      ),
    },
    {
      key: "category",
      header: t("memberColumns.category"),
      sortValue: (row) => row.category,
      cellClassName: "text-muted-foreground",
      cell: (row) => row.category ?? "—",
    },
    {
      key: "joinedAt",
      header: t("memberColumns.joinedAt"),
      sortValue: (row) => row.joined_at,
      cellClassName: "text-muted-foreground",
      cell: (row) => <DateCell value={row.joined_at} dateOnly />,
    },
    {
      key: "account",
      header: t("memberColumns.account"),
      sortValue: (row) => row.has_account,
      cell: (row) =>
        row.has_account ? (
          <Badge variant="outline">{t("hasAccount")}</Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
  ]

  return (
    <DataTable
      data={members}
      columns={columns}
      rowKey={(row) => row.id}
      locale={locale}
      defaultSort={{ key: "name", direction: "asc" }}
      searchPlaceholder={t("memberSearchPlaceholder")}
      searchFields={(row) => [row.first_name, row.last_name, row.member_number]}
      filters={[
        {
          key: "status",
          allLabel: t("filters.allStatuses"),
          options: statuses.map((status) => ({
            value: status,
            label: memberStatusLabel(tl, status),
          })),
          matches: (row, value) => row.status === value,
        },
      ]}
      emptyText={t("noMembers")}
    />
  )
}
