"use client"

import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import {
  DataTable,
  type DataTableColumn,
  type DataTableFilter,
} from "@/components/ui/data-table"
import { formatDate } from "@/lib/time"
import type { IncomingInvoice } from "@/lib/types/incoming-invoices"

function euro(amount: string, locale: string): string {
  return Number(amount).toLocaleString(locale, {
    style: "currency",
    currency: "EUR",
  })
}

/** Open and past its due date — the row a treasurer is looking for. */
function isOverdue(invoice: IncomingInvoice, today: string): boolean {
  return (
    invoice.status === "open" &&
    invoice.due_date !== null &&
    invoice.due_date < today
  )
}

export function InvoicesTable({
  invoices,
  timeZone,
  today,
}: {
  invoices: IncomingInvoice[]
  timeZone: string
  /** The club's today as an ISO date, stamped on the server. */
  today: string
}) {
  const t = useTranslations("invoices")
  const locale = useLocale()
  const router = useRouter()

  const columns: DataTableColumn<IncomingInvoice>[] = [
    {
      key: "supplier",
      header: t("columns.supplier"),
      sortValue: (row) => row.supplier_name ?? "",
      cell: (row) =>
        row.supplier_name ? (
          <span className="font-medium">{row.supplier_name}</span>
        ) : (
          // The filename is all this row knows so far, and it is what the
          // person who uploaded it will recognise.
          <span className="text-muted-foreground">{row.original_filename}</span>
        ),
    },
    {
      key: "number",
      header: t("columns.number"),
      shrink: true,
      sortValue: (row) => row.invoice_number ?? "",
      cellClassName: "tabular-nums text-muted-foreground",
      cell: (row) => row.invoice_number ?? "—",
    },
    {
      key: "date",
      header: t("columns.date"),
      shrink: true,
      sortValue: (row) => row.invoice_date ?? "",
      cellClassName: "tabular-nums",
      cell: (row) =>
        row.invoice_date ? formatDate(row.invoice_date, locale, timeZone) : "—",
    },
    {
      key: "amount",
      header: t("columns.amount"),
      align: "right",
      shrink: true,
      sortValue: (row) => Number(row.gross_amount ?? 0),
      cellClassName: "tabular-nums",
      cell: (row) => (row.gross_amount ? euro(row.gross_amount, locale) : "—"),
    },
    {
      key: "due",
      header: t("columns.due"),
      shrink: true,
      sortValue: (row) => row.due_date ?? "",
      cellClassName: "tabular-nums text-muted-foreground",
      cell: (row) =>
        row.due_date ? (
          <span
            className={isOverdue(row, today) ? "text-destructive" : undefined}
          >
            {formatDate(row.due_date, locale, timeZone)}
          </span>
        ) : (
          "—"
        ),
    },
    {
      key: "source",
      header: t("columns.source"),
      shrink: true,
      sortValue: (row) => row.source,
      // Only the exception is marked. Most rows will be typed, and a badge on
      // every one of those would make the column about nothing.
      cell: (row) =>
        row.source === "manual" ? null : (
          <Badge variant="secondary">{t("sources.electronic")}</Badge>
        ),
    },
    {
      key: "status",
      header: t("columns.status"),
      shrink: true,
      sortValue: (row) => row.status,
      cell: (row) => {
        if (!row.is_complete) {
          return <Badge variant="outline">{t("status.incomplete")}</Badge>
        }
        if (row.status === "cancelled") {
          return <Badge variant="outline">{t("status.cancelled")}</Badge>
        }
        if (row.status === "paid") {
          return <Badge variant="secondary">{t("status.paid")}</Badge>
        }
        return (
          <Badge variant={isOverdue(row, today) ? "destructive" : "outline"}>
            {isOverdue(row, today) ? t("status.overdue") : t("status.open")}
          </Badge>
        )
      },
    },
  ]

  const filters: DataTableFilter<IncomingInvoice>[] = [
    {
      key: "status",
      allLabel: t("filters.allStatuses"),
      matches: (row, value) => row.status === value,
      options: [
        { value: "open", label: t("status.open") },
        { value: "paid", label: t("status.paid") },
        { value: "cancelled", label: t("status.cancelled") },
      ],
    },
  ]

  return (
    <DataTable
      data={invoices}
      columns={columns}
      filters={filters}
      rowKey={(row) => row.id}
      onRowClick={(row) => router.push(`/incoming-invoices/${row.id}`)}
      searchPlaceholder={t("searchPlaceholder")}
      searchFields={(row) => [
        row.supplier_name,
        row.invoice_number,
        row.original_filename,
        row.note,
      ]}
      emptyText={t("empty")}
      noMatchText={t("noMatch")}
      locale={locale}
    />
  )
}
