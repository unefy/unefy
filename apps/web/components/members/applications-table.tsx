"use client"

import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import { DateCell } from "@/components/ui/date-cell"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import type { MembershipApplication } from "@/lib/types/application"

const STATUS_VARIANT = {
  pending: "default",
  accepted: "secondary",
  rejected: "outline",
} as const

/**
 * The applications a club has received.
 *
 * Rows lead to the detail page rather than deciding inline: admitting somebody
 * is not a click a board member should be able to make while scanning a list.
 */
export function ApplicationsTable({
  applications,
}: {
  applications: MembershipApplication[]
}) {
  const t = useTranslations("applications")
  const router = useRouter()
  const locale = useLocale()

  const columns: DataTableColumn<MembershipApplication>[] = [
    {
      key: "name",
      header: t("columns.name"),
      cell: (row) => (
        <span className="font-medium">
          {row.first_name} {row.last_name}
        </span>
      ),
      sortValue: (row) => `${row.last_name} ${row.first_name}`,
    },
    {
      key: "contact",
      header: t("columns.contact"),
      cell: (row) => (
        <span className="text-muted-foreground">
          {row.email ?? row.mobile ?? row.phone ?? "—"}
        </span>
      ),
      sortValue: (row) => row.email ?? row.mobile ?? row.phone,
    },
    {
      key: "created_at",
      header: t("columns.received"),
      cell: (row) => <DateCell value={row.created_at} />,
      sortValue: (row) => row.created_at,
      shrink: true,
    },
    {
      key: "status",
      header: t("columns.status"),
      cell: (row) => (
        <Badge variant={STATUS_VARIANT[row.status]}>
          {t(`status.${row.status}`)}
        </Badge>
      ),
      sortValue: (row) => row.status,
      shrink: true,
    },
  ]

  return (
    <DataTable
      data={applications}
      columns={columns}
      rowKey={(row) => row.id}
      onRowClick={(row) => router.push(`/applications/${row.id}`)}
      searchPlaceholder={t("search")}
      searchFields={(row) => [
        row.first_name,
        row.last_name,
        row.email,
        row.city,
      ]}
      filters={[
        {
          key: "status",
          allLabel: t("filters.allStatuses"),
          options: [
            { value: "pending", label: t("status.pending") },
            { value: "accepted", label: t("status.accepted") },
            { value: "rejected", label: t("status.rejected") },
          ],
          matches: (row, value) => row.status === value,
        },
      ]}
      defaultSort={{ key: "created_at", direction: "desc" }}
      emptyText={t("empty")}
      noMatchText={t("noMatch")}
      locale={locale}
    />
  )
}
