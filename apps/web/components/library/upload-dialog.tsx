"use client"

import { useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { toast } from "sonner"

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
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { folderOptions, formatBytes } from "@/lib/library-tree"
import type {
  LibraryDocument,
  LibraryFolder,
  LibraryVisibility,
} from "@/lib/types/library"

/** Sentinel for "no folder" — a Select value has to be a string. */
const ROOT = "root"

/**
 * Filing a document, or a new version of one.
 *
 * Sent with `XMLHttpRequest` rather than `fetch`, for one reason: only XHR
 * reports how far an upload has got. A scan takes long enough that a bar which
 * does not move is a bar somebody presses twice, and the second press is a
 * second copy of the same document.
 *
 * It posts to a route handler, not a server action — an action's body is
 * capped at 1 MB.
 *
 * The caller remounts this by changing its `key` on every opening, so the
 * fields start from the props each time. Resetting them in an effect instead
 * would mean a render with the previous document's title still on screen.
 */
export function UploadDialog({
  open,
  onOpenChange,
  folders,
  defaultFolderId = null,
  replacing,
  initialFile = null,
  maxUploadBytes,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  folders: LibraryFolder[]
  defaultFolderId?: string | null
  /** Set when filing a new version of an existing document. */
  replacing?: LibraryDocument
  /** Pre-selected by a drag onto the list. */
  initialFile?: File | null
  maxUploadBytes: number
}) {
  const t = useTranslations("library.upload")
  const tv = useTranslations("library.visibility")
  const locale = useLocale()
  const router = useRouter()
  const inputRef = useRef<HTMLInputElement>(null)

  const [file, setFile] = useState<File | null>(initialFile)
  const [title, setTitle] = useState(
    replacing?.title ?? stem(initialFile?.name) ?? ""
  )
  const [description, setDescription] = useState("")
  const [folderId, setFolderId] = useState<string>(defaultFolderId ?? ROOT)
  const [visibility, setVisibility] = useState<LibraryVisibility>(
    replacing?.visibility ?? "board"
  )
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const isVersion = replacing !== undefined

  function pick(chosen: File | null) {
    setFile(chosen)
    setError(null)
    // The title follows the filename until somebody types their own.
    if (chosen && !title.trim()) setTitle(stem(chosen.name) ?? "")
  }

  function submit() {
    if (!file) return
    if (file.size > maxUploadBytes) {
      // Politeness, not the check: the backend counts the bytes it receives.
      setError(t("errors.tooLarge", { limit: formatBytes(maxUploadBytes, locale) }))
      return
    }

    const body = new FormData()
    body.set("file", file)
    if (title.trim()) body.set("title", title.trim())
    if (description.trim()) body.set("description", description.trim())
    if (!isVersion) {
      if (folderId !== ROOT) body.set("folder_id", folderId)
      body.set("visibility", visibility)
    }

    const url = isVersion
      ? `/api/library/upload?documentId=${replacing.id}`
      : "/api/library/upload"

    setProgress(0)
    setError(null)

    const request = new XMLHttpRequest()
    request.open("POST", url)
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        setProgress(Math.round((event.loaded / event.total) * 100))
      }
    })
    request.addEventListener("load", () => {
      setProgress(null)
      if (request.status >= 200 && request.status < 300) {
        toast.success(isVersion ? t("versionFiled") : t("filed"))
        onOpenChange(false)
        router.refresh()
        return
      }
      setError(messageFor(request.responseText, t, locale, maxUploadBytes))
    })
    request.addEventListener("error", () => {
      setProgress(null)
      setError(t("errors.unreachable"))
    })
    request.send(body)
  }

  const busy = progress !== null

  return (
    <Dialog open={open} onOpenChange={busy ? () => {} : onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isVersion ? t("versionTitle") : t("title")}</DialogTitle>
          <DialogDescription>
            {isVersion
              ? t("versionDescription", { title: replacing.title })
              : t("description")}
          </DialogDescription>
        </DialogHeader>

        <DialogBody>
          <div className="space-y-2">
            <Label htmlFor="library-file">{t("file")}</Label>
            <Input
              id="library-file"
              ref={inputRef}
              type="file"
              disabled={busy}
              onChange={(event) => pick(event.target.files?.[0] ?? null)}
            />
            {file && (
              <p className="text-xs text-muted-foreground">
                {file.name} · {formatBytes(file.size, locale)}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="library-title">{t("documentTitle")}</Label>
            <Input
              id="library-title"
              value={title}
              disabled={busy}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={t("titlePlaceholder")}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="library-description">{t("note")}</Label>
            <Textarea
              id="library-description"
              rows={2}
              value={description}
              disabled={busy}
              onChange={(event) => setDescription(event.target.value)}
              placeholder={t("notePlaceholder")}
            />
          </div>

          {!isVersion && (
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="library-folder">{t("folder")}</Label>
                <Select
                  value={folderId}
                  onValueChange={(value) => setFolderId(String(value))}
                  disabled={busy}
                >
                  <SelectTrigger id="library-folder" className="w-full">
                    <SelectValue>
                      {(value: string) =>
                        value === ROOT
                          ? t("noFolder")
                          : (folderOptions(folders).find((o) => o.id === value)
                              ?.label ?? t("noFolder"))
                      }
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value={ROOT}>{t("noFolder")}</SelectItem>
                      {folderOptions(folders).map((option) => (
                        <SelectItem key={option.id} value={option.id}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="library-visibility">{t("visibility")}</Label>
                <Select
                  value={visibility}
                  onValueChange={(value) =>
                    setVisibility(value as LibraryVisibility)
                  }
                  disabled={busy}
                >
                  <SelectTrigger id="library-visibility" className="w-full">
                    <SelectValue>
                      {(value: string) => tv(value === "members" ? "members" : "board")}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="board">{tv("board")}</SelectItem>
                      <SelectItem value="members">{tv("members")}</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          {isVersion && (
            <p className="text-xs text-muted-foreground">{t("versionHint")}</p>
          )}

          {busy && (
            <div className="space-y-1">
              <Progress value={progress} aria-label={t("uploading")} />
              <p className="text-xs text-muted-foreground">
                {t("uploadingPercent", { percent: progress ?? 0 })}
              </p>
            </div>
          )}

          {error && <p className="text-sm text-destructive">{error}</p>}
        </DialogBody>

        <DialogFooter>
          <DialogClose
            render={
              <Button type="button" variant="outline" disabled={busy}>
                {t("cancel")}
              </Button>
            }
          />
          <Button onClick={submit} disabled={busy || !file || !title.trim()}>
            {busy ? t("uploading") : t("submit")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** A filename without its extension — the default title for an upload. */
function stem(filename: string | undefined): string | undefined {
  return filename?.replace(/\.[^.]+$/, "")
}

/**
 * The backend's error code turned into something a person can act on.
 *
 * "Too big" and "no space left" arrive as the same 413 and mean different
 * things: one is solved by scanning again at a lower resolution, the other by
 * clearing out or raising the quota.
 */
function messageFor(
  responseText: string,
  t: (key: string, values?: Record<string, string>) => string,
  locale: string,
  maxUploadBytes: number
): string {
  let code = ""
  try {
    code = (JSON.parse(responseText) as { error?: { code?: string } }).error
      ?.code as string
  } catch {
    code = ""
  }

  switch (code) {
    case "UNSUPPORTED_FILE_TYPE":
      return t("errors.type")
    case "UPLOAD_TOO_LARGE":
    case "PAYLOAD_TOO_LARGE":
      return t("errors.tooLarge", { limit: formatBytes(maxUploadBytes, locale) })
    case "STORAGE_QUOTA_EXCEEDED":
      return t("errors.quota")
    case "FORBIDDEN":
      return t("errors.forbidden")
    case "CONFLICT":
      return t("errors.superseded")
    default:
      return t("errors.unknown")
  }
}
