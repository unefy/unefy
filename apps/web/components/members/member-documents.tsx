"use client"

import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"
import { useLocale, useTranslations } from "next-intl"
import { toast } from "sonner"

import { issueDocumentAction, revokeDocumentAction } from "@/actions/documents"
import { ReasonDialog } from "@/components/attendance/reason-dialog"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import { DateCell } from "@/components/ui/date-cell"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { DocumentTemplate, IssuedDocument } from "@/lib/types/document"
import { DownloadIcon } from "lucide-react"

/**
 * Issuing a document for one member, and what has already been issued.
 *
 * Issuing is one button and no preview of this member's data: the wording was
 * proof-read when the template was written, and what changes per member is
 * their own details. A second confirmation here would be ceremony — the
 * document is revocable, which is the real safety net.
 */
export function MemberDocuments({
  memberId,
  templates,
  documents,
}: {
  memberId: string
  templates: DocumentTemplate[]
  documents: IssuedDocument[]
}) {
  const t = useTranslations("documents")
  const locale = useLocale()
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [templateId, setTemplateId] = useState(templates[0]?.id ?? "")

  function issue() {
    if (!templateId) return
    startTransition(async () => {
      const result = await issueDocumentAction(memberId, templateId)
      if (!result.success) {
        toast.error(t(`errors.${result.error}`))
        return
      }
      toast.success(t("issued"))
      router.refresh()
    })
  }

  const columns: DataTableColumn<IssuedDocument>[] = [
    {
      key: "title",
      header: t("columns.document"),
      cell: (row) => <span className="font-medium">{row.title}</span>,
      sortValue: (row) => row.title,
    },
    {
      key: "issued_at",
      header: t("columns.issuedAt"),
      cell: (row) => <DateCell value={row.issued_at} />,
      sortValue: (row) => row.issued_at,
      shrink: true,
    },
    {
      key: "status",
      header: t("columns.status"),
      cell: (row) =>
        row.revoked_at ? (
          <Badge variant="outline">{t("revoked")}</Badge>
        ) : (
          <Badge>{t("valid")}</Badge>
        ),
      sortValue: (row) => (row.revoked_at ? 1 : 0),
      shrink: true,
    },
    {
      key: "code",
      header: t("columns.code"),
      cell: (row) => (
        <span className="font-mono text-xs text-muted-foreground">
          {row.verification_code ?? "—"}
        </span>
      ),
      sortValue: (row) => row.verification_code,
      shrink: true,
    },
    {
      key: "actions",
      header: "",
      cell: (row) => (
        <div className="flex items-center justify-end gap-1">
          <a
            href={`/api/documents/${row.id}/pdf`}
            className={buttonVariants({ variant: "ghost", size: "sm" })}
            aria-label={t("download")}
          >
            <DownloadIcon className="size-4" />
          </a>
          {row.revoked_at ? null : (
            <ReasonDialog
              title={t("confirmRevoke.title")}
              description={t("confirmRevoke.description")}
              confirmLabel={t("revoke")}
              successMessage={t("revokedToast")}
              action={(reason) =>
                revokeDocumentAction(row.id, memberId, reason)
              }
              trigger={
                <span
                  className={buttonVariants({ variant: "ghost", size: "sm" })}
                >
                  {t("revoke")}
                </span>
              }
            />
          )}
        </div>
      ),
      shrink: true,
    },
  ]

  return (
    <div className="space-y-6">
      <section className="space-y-3 rounded-lg border p-4">
        <div className="space-y-1">
          <h2 className="text-sm font-medium">{t("issueTitle")}</h2>
          <p className="max-w-2xl text-sm text-muted-foreground">
            {t("issueHint")}
          </p>
        </div>

        {templates.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("noTemplates")}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-2">
              <Label htmlFor="issue-template">{t("fields.template")}</Label>
              <Select
                name="template"
                value={templateId}
                onValueChange={(value) => setTemplateId(String(value))}
              >
                <SelectTrigger id="issue-template" className="w-72">
                  {/* base-ui renders the raw value unless told otherwise, and
                      the value here is a uuid. */}
                  <SelectValue>
                    {(value: string) =>
                      templates.find((template) => template.id === value)
                        ?.name ?? ""
                    }
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {templates.map((template) => (
                    <SelectItem key={template.id} value={template.id}>
                      {template.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button onClick={issue} disabled={pending || !templateId}>
              {pending ? t("issuing") : t("issue")}
            </Button>
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium">{t("historyTitle")}</h2>
        <DataTable
          data={documents}
          columns={columns}
          rowKey={(row) => row.id}
          defaultSort={{ key: "issued_at", direction: "desc" }}
          emptyText={t("noDocuments")}
          locale={locale}
        />
        <p className="text-xs text-muted-foreground">{t("historyNote")}</p>
      </section>
    </div>
  )
}
