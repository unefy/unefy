"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import {
  bulkDeleteDocumentsAction,
  bulkUpdateDocumentsAction,
} from "@/actions/library"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { folderOptions } from "@/lib/library-tree"
import type { LibraryFolder, LibraryVisibility } from "@/lib/types/library"
import { Trash2Icon, XIcon } from "lucide-react"

const ROOT = "root"
/** The Select's resting state — picking an entry performs the move at once. */
const IDLE = "idle"

/**
 * What to do with the ticked rows.
 *
 * Appears only when something is ticked, so the ordinary view stays a list and
 * not a form. Every action reports how many documents it actually reached: a
 * club told "moved" when two of nine failed stops looking for the other two.
 */
export function BulkActions({
  selectedIds,
  folders,
  onDone,
}: {
  selectedIds: string[]
  folders: LibraryFolder[]
  onDone: () => void
}) {
  const t = useTranslations("library.bulk")
  const tv = useTranslations("library.visibility")
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [confirmOpen, setConfirmOpen] = useState(false)

  const count = selectedIds.length

  function report(result: {
    success: boolean
    data?: { ok: number; failed: number }
  }) {
    if (!result.success || !result.data) {
      toast.error(t("failed"))
      return
    }
    const { ok, failed } = result.data
    if (failed === 0) toast.success(t("done", { count: ok }))
    else toast.warning(t("partial", { ok, failed }))
    onDone()
    router.refresh()
  }

  function move(value: string) {
    if (value === IDLE) return
    startTransition(async () => {
      report(
        await bulkUpdateDocumentsAction(selectedIds, {
          folder_id: value === ROOT ? null : value,
        })
      )
    })
  }

  function setVisibility(value: string) {
    if (value === IDLE) return
    startTransition(async () => {
      report(
        await bulkUpdateDocumentsAction(selectedIds, {
          visibility: value as LibraryVisibility,
        })
      )
    })
  }

  function remove() {
    startTransition(async () => {
      setConfirmOpen(false)
      report(await bulkDeleteDocumentsAction(selectedIds))
    })
  }

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/40 px-3 py-2">
      <span className="text-sm font-medium">{t("selected", { count })}</span>

      <Select value={IDLE} onValueChange={(v) => move(String(v))} disabled={pending}>
        <SelectTrigger className="w-56" size="sm">
          <SelectValue>{() => t("moveTo")}</SelectValue>
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

      <Select
        value={IDLE}
        onValueChange={(v) => setVisibility(String(v))}
        disabled={pending}
      >
        <SelectTrigger className="w-48" size="sm">
          <SelectValue>{() => t("visibility")}</SelectValue>
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem value="board">{tv("board")}</SelectItem>
            <SelectItem value="members">{tv("members")}</SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogTrigger
          render={
            <Button variant="ghost" size="sm" disabled={pending}>
              <Trash2Icon className="text-destructive" />
              {t("delete")}
            </Button>
          }
        />
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("deleteTitle", { count })}</DialogTitle>
            <DialogDescription>{t("deleteDescription")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose
              render={<Button variant="outline">{t("cancel")}</Button>}
            />
            <Button variant="destructive" onClick={remove} disabled={pending}>
              {t("deleteConfirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Button
        variant="ghost"
        size="sm"
        className="ms-auto"
        onClick={onDone}
        disabled={pending}
      >
        <XIcon />
        {t("clear")}
      </Button>
    </div>
  )
}
