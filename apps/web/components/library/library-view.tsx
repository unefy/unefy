"use client"

import { useState } from "react"
import Link from "next/link"
import { useLocale, useTranslations } from "next-intl"

import { deleteDocumentAction, deleteFolderAction } from "@/actions/library"
import { ConfirmDelete } from "@/components/admin/confirm-delete"
import { DocumentDialog } from "@/components/library/document-dialog"
import { FolderDialog } from "@/components/library/folder-dialog"
import { FolderTree } from "@/components/library/folder-tree"
import { UploadDialog } from "@/components/library/upload-dialog"
import { Badge } from "@/components/ui/badge"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Button } from "@/components/ui/button"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
import { DateCell } from "@/components/ui/date-cell"
import { Progress } from "@/components/ui/progress"
import { folderPath, formatBytes } from "@/lib/library-tree"
import type {
  LibraryDocument,
  LibraryFolder,
  LibraryUsage,
} from "@/lib/types/library"
import { cn } from "@/lib/utils"
import {
  DownloadIcon,
  FileIcon,
  FileImageIcon,
  FileSpreadsheetIcon,
  FileTextIcon,
  FileUpIcon,
  UploadIcon,
} from "lucide-react"

/**
 * The library: drawers on the left, what is in the open one on the right.
 *
 * One client component rather than four, because the pieces share exactly one
 * thing — which file is about to be uploaded — and passing that between
 * siblings through the page would be more wiring than it is worth. Everything
 * that changes the server's mind still goes through an action or the upload
 * route; nothing here holds a copy of the truth.
 */
export function LibraryView({
  folders,
  documents,
  currentFolderId,
  usage,
  canEdit,
}: {
  folders: LibraryFolder[]
  documents: LibraryDocument[]
  currentFolderId: string | null
  usage: LibraryUsage | null
  canEdit: boolean
}) {
  const t = useTranslations("library")
  const tv = useTranslations("library.visibility")
  const locale = useLocale()

  // `key` counts openings: the dialog is remounted each time so its fields
  // start from these props instead of the previous document's.
  const [upload, setUpload] = useState<{
    open: boolean
    file: File | null
    replacing?: LibraryDocument
    key: number
  }>({ open: false, file: null, key: 0 })
  const [dragging, setDragging] = useState(false)

  const path = folderPath(folders, currentFolderId)
  const currentFolder = path.at(-1) ?? null
  const maxUploadBytes = usage?.max_upload_bytes ?? 25 * 1024 * 1024

  function openUpload(file: File | null, replacing?: LibraryDocument) {
    setUpload((state) => ({ open: true, file, replacing, key: state.key + 1 }))
  }

  const columns: DataTableColumn<LibraryDocument>[] = [
    {
      key: "title",
      header: t("columns.title"),
      sortValue: (row) => row.title,
      cell: (row) => (
        <div className="flex items-center gap-2">
          <DocumentIcon contentType={row.content_type} />
          <div className="min-w-0">
            <Link
              href={`/api/library/${row.id}/content`}
              target="_blank"
              rel="noopener"
              className="font-medium hover:underline"
            >
              {row.title}
            </Link>
            <p className="truncate text-xs text-muted-foreground">
              {row.description || row.original_filename}
            </p>
          </div>
        </div>
      ),
    },
    {
      key: "size",
      header: t("columns.size"),
      align: "right",
      shrink: true,
      sortValue: (row) => row.byte_size,
      cellClassName: "text-muted-foreground tabular-nums",
      cell: (row) => formatBytes(row.byte_size, locale),
    },
    {
      key: "uploadedAt",
      header: t("columns.uploadedAt"),
      shrink: true,
      sortValue: (row) => row.uploaded_at,
      cellClassName: "text-muted-foreground",
      cell: (row) => <DateCell value={row.uploaded_at} />,
    },
    {
      key: "visibility",
      header: t("columns.visibility"),
      shrink: true,
      sortValue: (row) => row.visibility,
      cell: (row) => (
        <Badge variant={row.visibility === "members" ? "secondary" : "outline"}>
          {tv(row.visibility)}
        </Badge>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      shrink: true,
      cell: (row) => (
        <div className="flex justify-end">
          <Button
            variant="ghost"
            size="sm"
            aria-label={t("download")}
            render={
              <a
                href={`/api/library/${row.id}/content`}
                target="_blank"
                rel="noopener"
              >
                <DownloadIcon />
              </a>
            }
          />
          {canEdit && (
            <>
              <Button
                variant="ghost"
                size="sm"
                aria-label={t("newVersion")}
                onClick={() => openUpload(null, row)}
              >
                <FileUpIcon />
              </Button>
              <DocumentDialog document={row} folders={folders} />
              <ConfirmDelete
                title={t("deleteTitle", { title: row.title })}
                description={t("deleteDescription")}
                action={() => deleteDocumentAction(row.id)}
              />
            </>
          )}
        </div>
      ),
    },
  ]

  return (
    <div className="grid gap-6 lg:grid-cols-[16rem_minmax(0,1fr)]">
      <aside className="lg:border-e lg:pe-4">
        <FolderTree
          folders={folders}
          currentId={currentFolderId}
          canEdit={canEdit}
        />
        {canEdit && usage && (
          <div className="mt-6 space-y-1 px-2">
            <Progress
              value={Math.min(
                100,
                Math.round((usage.used_bytes / Math.max(usage.quota_bytes, 1)) * 100)
              )}
              aria-label={t("usage")}
            />
            <p className="text-xs text-muted-foreground">
              {t("usageOf", {
                used: formatBytes(usage.used_bytes, locale),
                quota: formatBytes(usage.quota_bytes, locale),
              })}
            </p>
          </div>
        )}
      </aside>

      <section
        className={cn(
          "space-y-4 rounded-lg transition-colors",
          dragging && canEdit && "bg-accent/40 outline-2 outline-dashed outline-primary"
        )}
        onDragOver={(event) => {
          if (!canEdit) return
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          if (!canEdit) return
          event.preventDefault()
          setDragging(false)
          const dropped = event.dataTransfer.files[0]
          if (dropped) openUpload(dropped)
        }}
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                {currentFolder ? (
                  <BreadcrumbLink href="/library">{t("root")}</BreadcrumbLink>
                ) : (
                  <BreadcrumbPage>{t("root")}</BreadcrumbPage>
                )}
              </BreadcrumbItem>
              {path.map((folder, index) => (
                <span key={folder.id} className="contents">
                  <BreadcrumbSeparator />
                  <BreadcrumbItem>
                    {index === path.length - 1 ? (
                      <BreadcrumbPage>{folder.name}</BreadcrumbPage>
                    ) : (
                      <BreadcrumbLink href={`/library?folder=${folder.id}`}>
                        {folder.name}
                      </BreadcrumbLink>
                    )}
                  </BreadcrumbItem>
                </span>
              ))}
            </BreadcrumbList>
          </Breadcrumb>

          {canEdit && (
            <div className="flex items-center gap-1">
              {currentFolder && (
                <>
                  <FolderDialog folders={folders} folder={currentFolder} />
                  <ConfirmDelete
                    title={t("deleteFolderTitle", { name: currentFolder.name })}
                    description={t("deleteFolderDescription")}
                    action={async () => {
                      const result = await deleteFolderAction(currentFolder.id)
                      if (!result.success && result.error === "conflict") {
                        return { success: false, error: t("folderNotEmpty") }
                      }
                      return result
                    }}
                  />
                </>
              )}
              <Button size="sm" onClick={() => openUpload(null)}>
                <UploadIcon />
                {t("upload.submit")}
              </Button>
            </div>
          )}
        </div>

        <DataTable
          data={documents}
          columns={columns}
          rowKey={(row) => row.id}
          locale={locale}
          defaultSort={{ key: "uploadedAt", direction: "desc" }}
          searchPlaceholder={t("searchPlaceholder")}
          searchFields={(row) => [
            row.title,
            row.description,
            row.original_filename,
          ]}
          emptyText={canEdit ? t("emptyEditable") : t("empty")}
        />
      </section>

      {canEdit && (
        <UploadDialog
          key={upload.key}
          open={upload.open}
          onOpenChange={(open) => setUpload((state) => ({ ...state, open }))}
          folders={folders}
          defaultFolderId={currentFolderId}
          replacing={upload.replacing}
          initialFile={upload.file}
          maxUploadBytes={maxUploadBytes}
        />
      )}
    </div>
  )
}

/** A glance-level hint of what the file is — from the detected type, never
 * from the name it was uploaded under. */
function DocumentIcon({ contentType }: { contentType: string }) {
  const className = "size-4 shrink-0 text-muted-foreground"
  if (contentType.startsWith("image/")) return <FileImageIcon className={className} />
  if (contentType === "application/pdf") return <FileTextIcon className={className} />
  if (contentType.includes("spreadsheet") || contentType === "text/csv") {
    return <FileSpreadsheetIcon className={className} />
  }
  if (contentType.startsWith("text/") || contentType.includes("word")) {
    return <FileTextIcon className={className} />
  }
  return <FileIcon className={className} />
}
