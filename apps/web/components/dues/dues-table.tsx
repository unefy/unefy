"use client"

import { useTransition } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { toast } from "sonner"

import { cancelDueAction, reopenDueAction } from "@/actions/dues"
import { PayDueDialog } from "@/components/dues/pay-due-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DataTable,
  type DataTableColumn,
  type DataTableFilter,
} from "@/components/ui/data-table"
import { formatDate } from "@/lib/time"
import { DUE_STATUS_KEYS, type MyDue } from "@/lib/types/due"
import { BanIcon, RotateCcwIcon } from "lucide-react"

export function euro(amount: string, locale: string): string {
  return Number(amount).toLocaleString(locale, {
    style: "currency",
    currency: "EUR",
  })
}

/** An open due whose date has passed — the row a treasurer is looking for. */
function isOverdue(due: MyDue, today: string): boolean {
  return due.status === "open" && due.due_date < today
}

export function DuesTable({
  dues,
  timeZone,
  today,
  /** Board view: member column, booking actions. */
  canManage = false,
  showMember = false,
}: {
  dues: MyDue[]
  timeZone: string
  /** The club's today as an ISO date, stamped on the server. */
  today: string
  canManage?: boolean
  showMember?: boolean
}) {
  const t = useTranslations("dues")
  const locale = useLocale()
  const router = useRouter()
  const [pending, startTransition] = useTransition()

  function run(action: () => Promise<{ success: boolean; error?: string }>, message: string) {
    startTransition(async () => {
      const result = await action()
      if (result.success) {
        toast.success(message)
        router.refresh()
      } else {
        toast.error(t(`errors.${result.error}`))
      }
    })
  }

  const columns: DataTableColumn<MyDue>[] = []

  if (showMember) {
    columns.push({
      key: "member",
      header: t("columns.member"),
      sortValue: (row) => row.member_name,
      cell: (row) =>
        canManage && row.member_id ? (
          <Link
            href={`/members/${row.member_id}/dues`}
            className="font-medium hover:underline"
            onClick={(event) => event.stopPropagation()}
          >
            {row.member_name ?? "—"}
          </Link>
        ) : (
          <span className="font-medium">{row.member_name ?? "—"}</span>
        ),
    })
  }

  columns.push(
    {
      key: "fee",
      header: t("columns.fee"),
      sortValue: (row) => row.fee_name,
      cell: (row) => row.fee_name,
    },
    {
      key: "period",
      header: t("columns.period"),
      shrink: true,
      sortValue: (row) => row.period_start,
      cellClassName: "tabular-nums",
      cell: (row) => row.period_start.slice(0, 4),
    },
    {
      key: "amount",
      header: t("columns.amount"),
      align: "right",
      shrink: true,
      sortValue: (row) => Number(row.amount),
      cellClassName: "tabular-nums",
      cell: (row) => euro(row.amount, locale),
    },
    {
      key: "dueDate",
      header: t("columns.dueDate"),
      shrink: true,
      sortValue: (row) => row.due_date,
      cellClassName: "text-muted-foreground",
      cell: (row) => (
        <span className={isOverdue(row, today) ? "text-destructive" : undefined}>
          {formatDate(row.due_date, locale, timeZone)}
        </span>
      ),
    },
    {
      key: "status",
      header: t("columns.status"),
      shrink: true,
      sortValue: (row) => row.status,
      cell: (row) => (
        <Badge
          variant={
            row.status === "paid"
              ? "secondary"
              : isOverdue(row, today)
                ? "destructive"
                : "outline"
          }
        >
          {isOverdue(row, today)
            ? t("status.overdue")
            : t(`status.${row.status}`)}
        </Badge>
      ),
    },
    {
      key: "paidAt",
      header: t("columns.paidAt"),
      shrink: true,
      sortValue: (row) => row.paid_at,
      cellClassName: "text-muted-foreground",
      cell: (row) =>
        row.paid_at ? formatDate(row.paid_at, locale, timeZone) : "—",
    }
  )

  if (canManage) {
    columns.push({
      key: "actions",
      header: "",
      align: "right",
      shrink: true,
      cell: (row) => (
        <span className="flex items-center justify-end gap-1">
          {row.status === "open" ? (
            <>
              <PayDueDialog due={row} />
              <Button
                variant="ghost"
                size="sm"
                disabled={pending}
                aria-label={t("actions.cancel")}
                title={t("actions.cancel")}
                onClick={() =>
                  run(() => cancelDueAction(row.id), t("toasts.cancelled"))
                }
              >
                <BanIcon className="text-muted-foreground" />
              </Button>
            </>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              disabled={pending}
              aria-label={t("actions.reopen")}
              title={t("actions.reopen")}
              onClick={() =>
                run(() => reopenDueAction(row.id), t("toasts.reopened"))
              }
            >
              <RotateCcwIcon className="text-muted-foreground" />
            </Button>
          )}
        </span>
      ),
    })
  }

  const filters: DataTableFilter<MyDue>[] = [
    {
      key: "status",
      allLabel: t("filters.allStatuses"),
      options: [
        ...DUE_STATUS_KEYS.map((key) => ({
          value: key,
          label: t(`status.${key}`),
        })),
        { value: "overdue", label: t("status.overdue") },
      ],
      matches: (row, value) =>
        value === "overdue" ? isOverdue(row, today) : row.status === value,
    },
    {
      key: "year",
      allLabel: t("filters.allYears"),
      width: "w-32",
      options: [...new Set(dues.map((due) => due.period_start.slice(0, 4)))]
        .sort((a, b) => b.localeCompare(a))
        .map((year) => ({ value: year, label: year })),
      matches: (row, value) => row.period_start.startsWith(value),
    },
  ]

  return (
    <DataTable
      data={dues}
      columns={columns}
      rowKey={(row) => row.id}
      searchPlaceholder={t("searchPlaceholder")}
      searchFields={(row) => [row.member_name, row.fee_name, row.note]}
      filters={filters}
      defaultSort={{ key: "dueDate", direction: "desc" }}
      emptyText={t("empty")}
      locale={locale}
    />
  )
}
