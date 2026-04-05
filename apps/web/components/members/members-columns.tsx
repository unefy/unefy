"use client"

import type { ColumnDef } from "@tanstack/react-table"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import {
  getStatusLabel,
  type MemberStatusOption,
} from "@/lib/types/club"
import type { Member } from "@/lib/types/member"

function getStatusVariant(key: string): "default" | "secondary" | "outline" {
  if (key === "active") return "default"
  if (key === "inactive") return "secondary"
  return "outline"
}

interface BuildColumnsOptions {
  t: (key: string) => string
  memberStatuses: MemberStatusOption[]
  locale: string
}

export function buildMembersColumns({
  t,
  memberStatuses,
  locale,
}: BuildColumnsOptions): ColumnDef<Member>[] {
  return [
    {
      id: "select",
      size: 40,
      enableSorting: false,
      header: ({ table }) => (
        <div
          className="relative flex items-center"
          onClick={(e) => e.stopPropagation()}
        >
          <Checkbox
            checked={table.getIsAllRowsSelected()}
            indeterminate={
              table.getIsSomeRowsSelected() && !table.getIsAllRowsSelected()
            }
            onCheckedChange={(v) => table.toggleAllRowsSelected(v)}
            aria-label={t("selectAll")}
          />
        </div>
      ),
      cell: ({ row }) => (
        <div
          className="relative flex items-center"
          onClick={(e) => e.stopPropagation()}
        >
          <Checkbox
            checked={row.getIsSelected()}
            onCheckedChange={(v) => row.toggleSelected(!!v)}
            aria-label={t("selectRow")}
          />
        </div>
      ),
      meta: {
        cellClassName: "overflow-visible",
      },
    },
    {
      accessorKey: "member_number",
      size: 70,
      header: t("memberNumber"),
      cell: ({ getValue }) => (
        <span className="text-xs text-muted-foreground">
          {getValue<string>()}
        </span>
      ),
      meta: { sortField: "member_number" },
    },
    {
      accessorKey: "first_name",
      size: 140,
      header: t("firstName"),
      cell: ({ getValue }) => (
        <span className="font-medium">{getValue<string>()}</span>
      ),
      meta: { sortField: "first_name" },
    },
    {
      accessorKey: "last_name",
      size: 140,
      header: t("lastName"),
      cell: ({ getValue }) => (
        <span className="font-medium">{getValue<string>()}</span>
      ),
      meta: { sortField: "last_name" },
    },
    {
      accessorKey: "email",
      size: 260,
      header: t("email"),
      cell: ({ getValue }) => (
        <span className="text-muted-foreground">
          {getValue<string | null>() || "—"}
        </span>
      ),
      meta: {
        sortField: "email",
        headerClassName: "hidden md:table-cell",
        cellClassName: "hidden md:table-cell",
      },
    },
    {
      accessorKey: "status",
      size: 130,
      header: t("status"),
      cell: ({ getValue }) => {
        const key = getValue<string>()
        const s = memberStatuses.find((x) => x.key === key)
        return (
          <Badge variant={getStatusVariant(key)}>
            {s ? getStatusLabel(s, t) : key}
          </Badge>
        )
      },
      meta: { sortField: "status" },
    },
    {
      accessorKey: "joined_at",
      size: 120,
      header: t("joinedAt"),
      cell: ({ getValue }) => (
        <span className="text-muted-foreground">
          {new Date(getValue<string>()).toLocaleDateString(locale)}
        </span>
      ),
      meta: {
        sortField: "joined_at",
        headerClassName: "hidden lg:table-cell",
        cellClassName: "hidden lg:table-cell",
      },
    },
  ]
}
