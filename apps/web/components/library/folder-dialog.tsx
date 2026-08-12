"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { createFolderAction, updateFolderAction } from "@/actions/library"
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
import { descendantIds, folderOptions } from "@/lib/library-tree"
import type { LibraryFolder } from "@/lib/types/library"
import { FolderPlusIcon, PencilIcon } from "lucide-react"

/** Sentinel for "at the top level" — a Select value has to be a string. */
const ROOT = "root"

/**
 * Creating a drawer, renaming it, or moving it somewhere else.
 *
 * Moving a folder into its own subtree is refused by the backend; here those
 * options are simply not offered, so nobody gets an error where a missing
 * choice would have said the same thing more quietly.
 */
export function FolderDialog({
  folders,
  folder,
  parentId = null,
}: {
  folders: LibraryFolder[]
  /** Omitted when creating. */
  folder?: LibraryFolder
  /** Where a new folder lands — the drawer currently open. */
  parentId?: string | null
}) {
  const t = useTranslations("library.folderDialog")
  const tt = useTranslations("admin.toasts")
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  const isEdit = folder !== undefined
  const [name, setName] = useState(folder?.name ?? "")
  const [parent, setParent] = useState<string>(
    (isEdit ? folder.parent_id : parentId) ?? ROOT
  )

  const forbidden = isEdit ? descendantIds(folders, folder.id) : new Set<string>()
  const options = folderOptions(folders).filter(
    (option) => !forbidden.has(option.id)
  )

  function submit() {
    startTransition(async () => {
      const payload = {
        name: name.trim(),
        parent_id: parent === ROOT ? null : parent,
      }
      const result = isEdit
        ? await updateFolderAction(folder.id, payload)
        : await createFolderAction({ ...payload, sort_order: 0 })

      if (result.success) {
        setOpen(false)
        setError(null)
        toast.success(isEdit ? tt("saved") : tt("created"))
        router.refresh()
        return
      }
      setError(result.error === "conflict" ? t("nameTaken") : tt("error"))
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          isEdit ? (
            <Button variant="ghost" size="sm" aria-label={t("editTitle")}>
              <PencilIcon />
            </Button>
          ) : (
            <Button variant="ghost" size="sm" aria-label={t("createTitle")}>
              <FolderPlusIcon />
            </Button>
          )
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? t("editTitle") : t("createTitle")}</DialogTitle>
        </DialogHeader>

        <DialogBody>
          <div className="space-y-2">
            <Label htmlFor="folder-name">{t("name")}</Label>
            <Input
              id="folder-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={t("namePlaceholder")}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="folder-parent">{t("parent")}</Label>
            <Select
              value={parent}
              onValueChange={(value) => setParent(String(value))}
            >
              <SelectTrigger id="folder-parent" className="w-full">
                <SelectValue>
                  {(value: string) =>
                    value === ROOT
                      ? t("root")
                      : (options.find((option) => option.id === value)?.label ??
                        t("root"))
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value={ROOT}>{t("root")}</SelectItem>
                  {options.map((option) => (
                    <SelectItem key={option.id} value={option.id}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
            {isEdit && (
              <p className="text-xs text-muted-foreground">{t("moveHint")}</p>
            )}
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
          <Button onClick={submit} disabled={pending || !name.trim()}>
            {pending ? t("saving") : t("save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
