"use client"

import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"

import { deleteTemplateAction } from "@/actions/documents"
import { Badge } from "@/components/ui/badge"
import { ConfirmAction } from "@/components/ui/confirm-action"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import type { DocumentTemplate } from "@/lib/types/document"
import { Trash2Icon } from "lucide-react"

export function TemplatesTable({
  templates,
}: {
  templates: DocumentTemplate[]
}) {
  const t = useTranslations("documents")
  const router = useRouter()
  const locale = useLocale()

  const columns: DataTableColumn<DocumentTemplate>[] = [
    {
      key: "name",
      header: t("columns.name"),
      cell: (row) => <span className="font-medium">{row.name}</span>,
      sortValue: (row) => row.name,
    },
    {
      key: "title",
      header: t("columns.title"),
      cell: (row) => <span className="text-muted-foreground">{row.title}</span>,
      sortValue: (row) => row.title,
    },
    {
      key: "verifiable",
      header: t("columns.verifiable"),
      cell: (row) => (row.verifiable ? t("yes") : t("no")),
      sortValue: (row) => row.verifiable,
      shrink: true,
    },
    {
      key: "is_active",
      header: t("columns.status"),
      cell: (row) => (
        <Badge variant={row.is_active ? "default" : "outline"}>
          {row.is_active ? t("active") : t("inactive")}
        </Badge>
      ),
      sortValue: (row) => row.is_active,
      shrink: true,
    },
    {
      key: "actions",
      header: "",
      cell: (row) => (
        <ConfirmAction
          title={t("confirmDelete.title")}
          description={t("confirmDelete.description", { name: row.name })}
          confirmLabel={t("delete")}
          successMessage={t("deleted")}
          action={() => deleteTemplateAction(row.id)}
          trigger={
            <span
              className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent"
              aria-label={t("delete")}
            >
              <Trash2Icon className="size-4" />
            </span>
          }
        />
      ),
      shrink: true,
    },
  ]

  return (
    <DataTable
      data={templates}
      columns={columns}
      rowKey={(row) => row.id}
      onRowClick={(row) => router.push(`/settings/documents/${row.id}`)}
      searchPlaceholder={t("search")}
      searchFields={(row) => [row.name, row.title]}
      defaultSort={{ key: "name", direction: "asc" }}
      emptyText={t("empty")}
      noMatchText={t("noMatch")}
      locale={locale}
    />
  )
}
