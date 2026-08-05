"use client"

import { useMemo } from "react"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import { DateCell } from "@/components/ui/date-cell"
import { memberStatusLabel } from "@/lib/labels"
import type { Member } from "@/lib/types/member"

export function MembersTable({ members }: { members: Member[] }) {
  const t = useTranslations("members")
  const tl = useTranslations("admin")
  const locale = useLocale()
  const router = useRouter()

  // Statuses and categories are club-defined, so both filters offer what
  // actually occurs rather than a hard-coded list.
  const statuses = useMemo(
    () => [...new Set(members.map((m) => m.status))].sort(),
    [members]
  )
  const categories = useMemo(
    () =>
      [
        ...new Set(members.map((m) => m.category).filter(Boolean)),
      ].sort() as string[],
    [members]
  )

  const columns: DataTableColumn<Member>[] = [
    {
      key: "lastName",
      header: t("columns.lastName"),
      sortValue: (row) => `${row.last_name} ${row.first_name}`,
      cell: (row) => <span className="font-medium">{row.last_name}</span>,
    },
    {
      key: "firstName",
      header: t("columns.firstName"),
      sortValue: (row) => `${row.first_name} ${row.last_name}`,
      cell: (row) => row.first_name,
    },
    {
      key: "memberNumber",
      header: t("columns.memberNumber"),
      shrink: true,
      sortValue: (row) => row.member_number,
      cellClassName: "font-mono text-xs text-muted-foreground",
      cell: (row) => row.member_number,
    },
    {
      key: "email",
      header: t("columns.email"),
      sortValue: (row) => row.email,
      cellClassName: "text-muted-foreground",
      cell: (row) => row.email ?? "—",
    },
    {
      key: "status",
      header: t("columns.status"),
      sortValue: (row) => memberStatusLabel(tl, row.status),
      cell: (row) => (
        <Badge variant="secondary">{memberStatusLabel(tl, row.status)}</Badge>
      ),
    },
    {
      key: "category",
      header: t("columns.category"),
      sortValue: (row) => row.category,
      cellClassName: "text-muted-foreground",
      cell: (row) => row.category ?? "—",
    },
    {
      key: "joinedAt",
      header: t("columns.joinedAt"),
      shrink: true,
      sortValue: (row) => row.joined_at,
      cellClassName: "text-muted-foreground",
      cell: (row) => <DateCell value={row.joined_at} dateOnly />,
    },
  ]

  return (
    <DataTable
      data={members}
      columns={columns}
      rowKey={(row) => row.id}
      locale={locale}
      defaultSort={{ key: "lastName", direction: "asc" }}
      searchPlaceholder={t("searchPlaceholder")}
      searchFields={(row) => [
        row.first_name,
        row.last_name,
        row.member_number,
        row.email,
      ]}
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
        ...(categories.length > 0
          ? [
              {
                key: "category",
                allLabel: t("filters.allCategories"),
                options: categories.map((c) => ({ value: c, label: c })),
                matches: (row: Member, value: string) => row.category === value,
              },
            ]
          : []),
      ]}
      onRowClick={(row) => router.push(`/members/${row.id}`)}
      emptyText={t("empty")}
    />
  )
}
