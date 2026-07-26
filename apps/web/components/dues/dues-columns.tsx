"use client"

import type { ColumnDef } from "@tanstack/react-table"
import { Badge } from "@/components/ui/badge"
import { formatDate } from "@/lib/date"
import { formatCurrency } from "@/lib/currency"
import type { Due, DueStatus } from "@/lib/types/due"

function getStatusVariant(status: DueStatus): "default" | "secondary" | "outline" {
  if (status === "open") return "default"
  if (status === "paid") return "secondary"
  return "outline"
}

interface BuildDuesColumnsOptions {
  t: (key: string) => string
  locale: string
  actionsCell: ColumnDef<Due>["cell"]
}

export function buildDuesColumns({
  t,
  locale,
  actionsCell,
}: BuildDuesColumnsOptions): ColumnDef<Due>[] {
  return [
    {
      accessorKey: "member_name",
      size: 180,
      header: t("member"),
      enableSorting: false,
      cell: ({ getValue }) => (
        <span className="font-medium">{getValue<string | null>() || "—"}</span>
      ),
    },
    {
      accessorKey: "fee_name",
      size: 160,
      header: t("feeType"),
      enableSorting: false,
      cell: ({ getValue }) => <span>{getValue<string>()}</span>,
    },
    {
      accessorKey: "period_start",
      size: 180,
      header: t("period"),
      enableSorting: false,
      cell: ({ row }) => (
        <span className="text-muted-foreground">
          {formatDate(row.original.period_start, locale)} –{" "}
          {formatDate(row.original.period_end, locale)}
        </span>
      ),
      meta: {
        headerClassName: "hidden md:table-cell",
        cellClassName: "hidden md:table-cell",
      },
    },
    {
      accessorKey: "due_date",
      size: 110,
      header: t("dueDate"),
      enableSorting: false,
      cell: ({ getValue }) => (
        <span className="text-muted-foreground">
          {formatDate(getValue<string>(), locale)}
        </span>
      ),
      meta: {
        headerClassName: "hidden lg:table-cell",
        cellClassName: "hidden lg:table-cell",
      },
    },
    {
      accessorKey: "amount",
      size: 100,
      header: t("amount"),
      enableSorting: false,
      cell: ({ getValue }) => (
        <span className="font-medium tabular-nums">
          {formatCurrency(getValue<string>(), locale)}
        </span>
      ),
    },
    {
      accessorKey: "status",
      size: 110,
      header: t("status"),
      enableSorting: false,
      cell: ({ getValue }) => {
        const status = getValue<DueStatus>()
        return (
          <Badge variant={getStatusVariant(status)}>
            {t(`status_${status}`)}
          </Badge>
        )
      },
    },
    {
      id: "actions",
      size: 50,
      enableSorting: false,
      header: "",
      cell: actionsCell,
    },
  ]
}
