"use client"

import { useLocale, useTranslations } from "next-intl"

import { DownloadIcon } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import { RevokeDialog } from "@/components/shooting/revoke-dialog"
import { formatDate } from "@/lib/time"
import type { ShootingCertificate } from "@/lib/types/shooting"

export function CertificatesTable({
  certificates,
  timeZone,
}: {
  certificates: ShootingCertificate[]
  timeZone: string
}) {
  const t = useTranslations("shooting.certificates")
  const locale = useLocale()

  const columns: DataTableColumn<ShootingCertificate>[] = [
    {
      key: "issuedAt",
      header: t("columns.issuedAt"),
      shrink: true,
      sortValue: (row) => row.issued_at,
      cell: (row) => formatDate(row.issued_at, locale, timeZone),
    },
    {
      key: "member",
      header: t("columns.member"),
      sortValue: (row) => row.member_name,
      cell: (row) => <span className="font-medium">{row.member_name}</span>,
    },
    {
      key: "rule",
      header: t("columns.rule"),
      shrink: true,
      cellClassName: "text-muted-foreground font-mono text-xs",
      cell: (row) => row.rule_key,
    },
    {
      key: "period",
      header: t("columns.period"),
      cellClassName: "text-muted-foreground tabular-nums",
      // Calendar dates — UTC keeps the day from shifting with the viewer.
      cell: (row) =>
        `${formatDate(row.period_start, locale, "UTC")} – ${formatDate(row.period_end, locale, "UTC")}`,
    },
    {
      key: "sessions",
      header: t("columns.sessions"),
      align: "center",
      shrink: true,
      sortValue: (row) => row.session_count,
      cellClassName: "tabular-nums",
      cell: (row) => row.session_count,
    },
    {
      key: "result",
      header: t("columns.result"),
      shrink: true,
      sortValue: (row) => row.result,
      cell: (row) =>
        row.result === "passed" ? (
          <Badge>{t("passed")}</Badge>
        ) : (
          <Badge variant="destructive">{t("failed")}</Badge>
        ),
    },
    {
      key: "status",
      header: t("columns.status"),
      shrink: true,
      sortValue: (row) => (row.revoked_at ? "revoked" : "valid"),
      cell: (row) =>
        row.revoked_at ? (
          <Badge variant="secondary">{t("revoked")}</Badge>
        ) : (
          <Badge variant="outline">{t("valid")}</Badge>
        ),
    },
    {
      key: "code",
      header: t("columns.code"),
      shrink: true,
      cellClassName: "font-mono text-xs text-muted-foreground",
      cell: (row) => row.verification_code,
    },
    {
      key: "actions",
      header: "",
      align: "right",
      shrink: true,
      cell: (row) => (
        <span className="flex items-center justify-end gap-1">
          {/* Navigation, not fetch: the browser handles the download. Offered
              for revoked ones too — a withdrawn proof still has to be
              producible, and the PDF says on its face that it was revoked. */}
          <Button
            variant="ghost"
            size="sm"
            aria-label={t("download")}
            title={t("download")}
            render={
              <a href={`/api/shooting/certificate?id=${row.id}`} download>
                <DownloadIcon className="text-muted-foreground" />
              </a>
            }
          />
          {row.revoked_at === null ? <RevokeDialog certificate={row} /> : null}
        </span>
      ),
    },
  ]

  return (
    <DataTable
      data={certificates}
      columns={columns}
      rowKey={(row) => row.id}
      locale={locale}
      defaultSort={{ key: "issuedAt", direction: "desc" }}
      searchPlaceholder={t("searchPlaceholder")}
      searchFields={(row) => [
        row.member_name,
        row.rule_key,
        row.verification_code,
      ]}
      emptyText={t("empty")}
    />
  )
}
