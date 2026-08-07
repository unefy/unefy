"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import {
  createFunctionAction,
  updateFunctionAction,
} from "@/actions/functions"
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
import { Switch } from "@/components/ui/switch"
import { roleLabel, ROLE_KEYS } from "@/lib/labels"
import type { ClubFunction, FunctionLevel } from "@/lib/types/functions"
import { PencilIcon, PlusIcon } from "lucide-react"

/** Sentinel for "no suggested role" — Select values must be strings. */
const NO_ROLE = "none"

export function FunctionDialog({
  func,
  hasDivisions,
}: {
  /** Omitted when creating. */
  func?: ClubFunction
  /** Clubs without divisions never see the level choice — everything is club-level. */
  hasDivisions: boolean
}) {
  const t = useTranslations("clubSettings.functions.dialog")
  const tl = useTranslations("clubSettings.functions")
  const tr = useTranslations("admin")
  const tt = useTranslations("admin.toasts")
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  const [name, setName] = useState(func?.name ?? "")
  const [level, setLevel] = useState<FunctionLevel>(func?.level ?? "club")
  const [suggestedRole, setSuggestedRole] = useState<string>(
    func?.suggested_role ?? NO_ROLE
  )
  const [sortOrder, setSortOrder] = useState(String(func?.sort_order ?? 0))
  const [isActive, setIsActive] = useState(func?.is_active ?? true)

  const isEdit = func !== undefined

  function submit() {
    startTransition(async () => {
      const payload = {
        name,
        level,
        suggested_role:
          suggestedRole === NO_ROLE
            ? null
            : (suggestedRole as (typeof ROLE_KEYS)[number]),
        sort_order: Number(sortOrder) || 0,
        is_active: isActive,
      }
      const result = isEdit
        ? await updateFunctionAction(func.id, payload)
        : await createFunctionAction(payload)

      if (result.success) {
        setOpen(false)
        setError(null)
        toast.success(isEdit ? tt("saved") : tt("created"))
        router.refresh()
      } else {
        setError(
          result.error === "conflict" ? t("nameTaken") : tt("error")
        )
      }
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          isEdit ? (
            <Button variant="ghost" size="sm" aria-label={t("edit")}>
              <PencilIcon />
            </Button>
          ) : (
            <Button size="sm">
              <PlusIcon />
              {t("create")}
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
            <Label htmlFor="function-name">{t("name")}</Label>
            <Input
              id="function-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("namePlaceholder")}
            />
          </div>

          {hasDivisions && (
            <div className="space-y-2">
              <Label htmlFor="function-level">{t("level")}</Label>
              <Select
                value={level}
                onValueChange={(value) => setLevel(value as FunctionLevel)}
              >
                <SelectTrigger id="function-level" className="w-full">
                  <SelectValue>
                    {(value: string) => tl(`levels.${value}`)}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="club">{tl("levels.club")}</SelectItem>
                    <SelectItem value="division">
                      {tl("levels.division")}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">{t("levelHint")}</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="function-role">{t("suggestedRole")}</Label>
              <Select
                value={suggestedRole}
                onValueChange={(value) => setSuggestedRole(String(value))}
              >
                <SelectTrigger id="function-role" className="w-full">
                  <SelectValue>
                    {(value: string) =>
                      value === NO_ROLE ? t("noRole") : roleLabel(tr, value)
                    }
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value={NO_ROLE}>{t("noRole")}</SelectItem>
                    {ROLE_KEYS.map((role) => (
                      <SelectItem key={role} value={role}>
                        {roleLabel(tr, role)}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="function-sort">{t("sortOrder")}</Label>
              <Input
                id="function-sort"
                type="number"
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value)}
              />
            </div>
          </div>

          {isEdit && (
            <div className="flex items-center justify-between rounded-md border p-3">
              <div className="space-y-0.5">
                <Label htmlFor="function-active">{t("active")}</Label>
                <p className="text-xs text-muted-foreground">
                  {t("activeHint")}
                </p>
              </div>
              <Switch
                id="function-active"
                checked={isActive}
                onCheckedChange={setIsActive}
              />
            </div>
          )}

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
