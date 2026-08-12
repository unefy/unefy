"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { updateDocumentAction } from "@/actions/library"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { folderOptions } from "@/lib/library-tree"
import type {
  LibraryDocument,
  LibraryFolder,
  LibraryVisibility,
} from "@/lib/types/library"
import { PencilIcon } from "lucide-react"

const ROOT = "root"

/**
 * Title, note, drawer and who may see it.
 *
 * Never the file itself: replacing the bytes is filing a new version, so what
 * was filed stays what was filed.
 */
export function DocumentDialog({
  document,
  folders,
}: {
  document: LibraryDocument
  folders: LibraryFolder[]
}) {
  const t = useTranslations("library.edit")
  const tv = useTranslations("library.visibility")
  const tt = useTranslations("admin.toasts")
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  const [title, setTitle] = useState(document.title)
  const [description, setDescription] = useState(document.description ?? "")
  const [folderId, setFolderId] = useState<string>(document.folder_id ?? ROOT)
  const [visibility, setVisibility] = useState<LibraryVisibility>(
    document.visibility
  )

  const options = folderOptions(folders)

  function submit() {
    startTransition(async () => {
      const result = await updateDocumentAction(document.id, {
        title: title.trim(),
        description: description.trim() || null,
        folder_id: folderId === ROOT ? null : folderId,
        visibility,
      })
      if (result.success) {
        setOpen(false)
        setError(null)
        toast.success(tt("saved"))
        router.refresh()
        return
      }
      setError(tt("error"))
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="ghost" size="sm" aria-label={t("title")}>
            <PencilIcon />
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
        </DialogHeader>

        <DialogBody>
          <div className="space-y-2">
            <Label htmlFor="document-title">{t("documentTitle")}</Label>
            <Input
              id="document-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="document-description">{t("note")}</Label>
            <Textarea
              id="document-description"
              rows={2}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="document-folder">{t("folder")}</Label>
              <Select
                value={folderId}
                onValueChange={(value) => setFolderId(String(value))}
              >
                <SelectTrigger id="document-folder" className="w-full">
                  <SelectValue>
                    {(value: string) =>
                      value === ROOT
                        ? t("noFolder")
                        : (options.find((option) => option.id === value)
                            ?.label ?? t("noFolder"))
                    }
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value={ROOT}>{t("noFolder")}</SelectItem>
                    {options.map((option) => (
                      <SelectItem key={option.id} value={option.id}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="document-visibility">{t("visibility")}</Label>
              <Select
                value={visibility}
                onValueChange={(value) =>
                  setVisibility(value as LibraryVisibility)
                }
              >
                <SelectTrigger id="document-visibility" className="w-full">
                  <SelectValue>
                    {(value: string) =>
                      tv(value === "members" ? "members" : "board")
                    }
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="board">{tv("board")}</SelectItem>
                    <SelectItem value="members">{tv("members")}</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {tv(`${visibility}Hint`)}
              </p>
            </div>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </DialogBody>

        <DialogFooter>
          <DialogClose
            render={
              <Button type="button" variant="outline">
                {t("cancel")}
              </Button>
            }
          />
          <Button onClick={submit} disabled={pending || !title.trim()}>
            {pending ? t("saving") : t("save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
