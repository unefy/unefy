"use client"

import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import {
  DataTable,
  type DataTableColumn,
  type DataTableFilter,
} from "@/components/ui/data-table"
import { formatDateTime } from "@/lib/time"
import type { Message } from "@/lib/types/message"

/** sent / skipped / failed, in that order, as one column. */
function tally(message: Message): [number, number, number] {
  return [
    message.counts.sent ?? 0,
    message.counts.skipped ?? 0,
    message.counts.failed ?? 0,
  ]
}

export function MessagesTable({
  messages,
  timeZone,
}: {
  messages: Message[]
  timeZone: string
}) {
  const t = useTranslations("messages")
  const locale = useLocale()
  const router = useRouter()

  const columns: DataTableColumn<Message>[] = [
    {
      key: "subject",
      header: t("columns.subject"),
      sortValue: (row) => row.subject,
      cell: (row) => <span className="font-medium">{row.subject}</span>,
    },
    {
      key: "kind",
      header: t("columns.kind"),
      shrink: true,
      sortValue: (row) => row.kind,
      cell: (row) => <Badge variant="outline">{t(`kinds.${row.kind}`)}</Badge>,
    },
    {
      key: "queued",
      header: t("columns.queued"),
      shrink: true,
      sortValue: (row) => row.queued_at,
      cellClassName: "tabular-nums text-muted-foreground",
      cell: (row) => formatDateTime(row.queued_at, locale, timeZone),
    },
    {
      key: "tally",
      header: t("columns.tally"),
      align: "right",
      shrink: true,
      sortValue: (row) => tally(row)[0],
      cellClassName: "tabular-nums",
      // One cell rather than three columns: the three numbers are read
      // together — "143 out, 12 not, 3 broken" — and apart they invite
      // sorting by a figure that means nothing on its own.
      cell: (row) => {
        const [sent, skipped, failed] = tally(row)
        return (
          <span>
            {sent}
            <span className="text-muted-foreground"> / {skipped} / </span>
            <span
              className={
                failed > 0 ? "text-destructive" : "text-muted-foreground"
              }
            >
              {failed}
            </span>
          </span>
        )
      },
    },
    {
      key: "status",
      header: t("columns.status"),
      shrink: true,
      sortValue: (row) => row.status,
      cell: (row) => (
        <Badge
          variant={
            row.status === "failed"
              ? "destructive"
              : row.status === "done"
                ? "secondary"
                : "outline"
          }
        >
          {t(`statuses.${row.status}`)}
        </Badge>
      ),
    },
  ]

  const filters: DataTableFilter<Message>[] = [
    {
      key: "kind",
      allLabel: t("filters.allKinds"),
      matches: (row, value) => row.kind === value,
      options: [
        { value: "notice", label: t("kinds.notice") },
        { value: "newsletter", label: t("kinds.newsletter") },
      ],
    },
  ]

  return (
    <DataTable
      data={messages}
      columns={columns}
      filters={filters}
      rowKey={(row) => row.id}
      onRowClick={(row) => router.push(`/messages/${row.id}`)}
      searchPlaceholder={t("searchPlaceholder")}
      searchFields={(row) => [row.subject, row.body]}
      emptyText={t("empty")}
      noMatchText={t("noMatch")}
      locale={locale}
    />
  )
}
