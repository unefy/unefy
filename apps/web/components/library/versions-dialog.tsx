"use client"

import { useState, useTransition } from "react"
import { useLocale, useTranslations } from "next-intl"

import { listVersionsAction } from "@/actions/library"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { DateCell } from "@/components/ui/date-cell"
import { Skeleton } from "@/components/ui/skeleton"
import { formatBytes } from "@/lib/library-tree"
import type { LibraryDocument } from "@/lib/types/library"
import { DownloadIcon, HistoryIcon } from "lucide-react"

/**
 * Which editions of this document there have been, and which one applied when.
 *
 * The chain is fetched when the dialog opens rather than sent with every row:
 * a list of thirty documents would otherwise carry the history of all thirty
 * to answer a question nobody asked.
 */
export function VersionsDialog({ document }: { document: LibraryDocument }) {
  const t = useTranslations("library.versions")
  const locale = useLocale()
  const [open, setOpen] = useState(false)
  const [versions, setVersions] = useState<LibraryDocument[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  function load(next: boolean) {
    setOpen(next)
    if (!next) return
    setVersions(null)
    setError(null)
    startTransition(async () => {
      const result = await listVersionsAction(document.id)
      if (result.success) setVersions(result.data ?? [])
      else setError(t("failed"))
    })
  }

  return (
    <Dialog open={open} onOpenChange={load}>
      <DialogTrigger
        render={
          <Button variant="ghost" size="sm" aria-label={t("title")}>
            <HistoryIcon />
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
          <DialogDescription>
            {t("description", { title: document.title })}
          </DialogDescription>
        </DialogHeader>

        <DialogBody>
          {pending && !versions && (
            <div className="space-y-2">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          )}

          {error && <p className="text-sm text-destructive">{error}</p>}

          {versions && (
            <ol className="divide-y rounded-md border">
              {versions.map((version, index) => (
                <li
                  key={version.id}
                  className="flex items-center justify-between gap-3 p-3"
                >
                  <div className="min-w-0 space-y-0.5">
                    <p className="truncate text-sm font-medium">
                      {version.original_filename}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatBytes(version.byte_size, locale)} ·{" "}
                      <DateCell value={version.uploaded_at} />
                      {version.superseded_at ? (
                        <>
                          {" · "}
                          {t("supersededOn")}{" "}
                          <DateCell value={version.superseded_at} />
                        </>
                      ) : (
                        <> · {index === 0 ? t("current") : ""}</>
                      )}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={t("download")}
                    render={
                      <a
                        href={`/api/library/${version.id}/content`}
                        target="_blank"
                        rel="noopener"
                      >
                        <DownloadIcon />
                      </a>
                    }
                  />
                </li>
              ))}
            </ol>
          )}

          {versions?.length === 1 && (
            <p className="text-xs text-muted-foreground">{t("onlyOne")}</p>
          )}
        </DialogBody>

        <DialogFooter>
          <DialogClose
            render={<Button variant="outline">{t("close")}</Button>}
          />
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
