"use client"

import { useLocale, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import {
  DataTable,
  type DataTableColumn,
  type DataTableFilter,
} from "@/components/ui/data-table"
import { formatDateTime } from "@/lib/time"
import type { MessageRecipient } from "@/lib/types/message"

/**
 * Who got it, and who did not.
 *
 * The screen exists for the second half of that sentence, so the reason is a
 * column of its own rather than something to hover for: "übersprungen" alone
 * would send a board member looking through consents for somebody who simply
 * has no address on file.
 */
export function RecipientsTable({
  recipients,
  timeZone,
}: {
  recipients: MessageRecipient[]
  timeZone: string
}) {
  const t = useTranslations("messages")
  const locale = useLocale()

  const columns: DataTableColumn<MessageRecipient>[] = [
    {
      key: "email",
      header: t("recipients.email"),
      sortValue: (row) => row.email ?? "",
      cell: (row) =>
        row.email ?? <span className="text-muted-foreground">—</span>,
    },
    {
      key: "status",
      header: t("recipients.status"),
      shrink: true,
      sortValue: (row) => row.status,
      cell: (row) => (
        <Badge
          variant={
            row.status === "failed"
              ? "destructive"
              : row.status === "sent"
                ? "secondary"
                : "outline"
          }
        >
          {t(`recipientStatuses.${row.status}`)}
        </Badge>
      ),
    },
    {
      key: "reason",
      header: t("recipients.reason"),
      shrink: true,
      sortValue: (row) => row.reason ?? "",
      cellClassName: "text-muted-foreground",
      cell: (row) =>
        row.reason ? t(`reasons.${row.reason}`) : (row.error ?? "—"),
    },
    {
      key: "sent",
      header: t("recipients.sentAt"),
      shrink: true,
      sortValue: (row) => row.sent_at ?? "",
      cellClassName: "tabular-nums text-muted-foreground",
      cell: (row) =>
        row.sent_at ? formatDateTime(row.sent_at, locale, timeZone) : "—",
    },
  ]

  const filters: DataTableFilter<MessageRecipient>[] = [
    {
      key: "status",
      allLabel: t("recipients.allStatuses"),
      matches: (row, value) => row.status === value,
      options: [
        { value: "sent", label: t("recipientStatuses.sent") },
        { value: "skipped", label: t("recipientStatuses.skipped") },
        { value: "failed", label: t("recipientStatuses.failed") },
        { value: "pending", label: t("recipientStatuses.pending") },
      ],
    },
  ]

  return (
    <DataTable
      data={recipients}
      columns={columns}
      filters={filters}
      rowKey={(row) => row.id}
      searchPlaceholder={t("recipients.search")}
      searchFields={(row) => [row.email, row.error]}
      emptyText={t("recipients.empty")}
      noMatchText={t("noMatch")}
      locale={locale}
    />
  )
}
