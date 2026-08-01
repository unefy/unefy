"use client"

import { useActionState, useState } from "react"
import { useTranslations } from "next-intl"

import { impersonateAction } from "@/actions/admin"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
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
import { roleLabel } from "@/lib/labels"
import type { AdminMembership } from "@/lib/types/admin"
import { UserCogIcon } from "lucide-react"

type ImpersonateDialogProps = {
  userId: string
  userName: string
  userEmail: string
  memberships: AdminMembership[]
  disabled?: boolean
}

/**
 * Starts an impersonation session.
 *
 * The reason field is required and stored in the audit log — impersonation is
 * a privileged act, and a record of *why* is what makes it reviewable later.
 */
export function ImpersonateDialog({
  userId,
  userName,
  userEmail,
  memberships,
  disabled,
}: ImpersonateDialogProps) {
  const t = useTranslations("admin.impersonate")
  const tl = useTranslations("admin")
  const [open, setOpen] = useState(false)
  const [state, formAction, pending] = useActionState(
    impersonateAction,
    undefined
  )

  // Rendered on a single user's detail page, so `memberships` never changes
  // for a given instance — the initial value is the whole story.
  const active = memberships.filter((m) => m.is_active)
  const [tenantId, setTenantId] = useState(active[0]?.tenant_id ?? "")

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="outline" size="sm" disabled={disabled}>
            <UserCogIcon />
            {t("action")}
          </Button>
        }
      />
      <DialogContent>
        <form action={formAction}>
          <input type="hidden" name="user_id" value={userId} />
          <input type="hidden" name="tenant_id" value={tenantId} />

          <DialogHeader>
            <DialogTitle>{t("title")}</DialogTitle>
            <DialogDescription>
              {t("description", { name: userName, email: userEmail })}
            </DialogDescription>
          </DialogHeader>

          <DialogBody>
            {active.length > 1 && (
              <div className="space-y-2">
                <Label htmlFor="impersonate-club">{t("club")}</Label>
                <Select
                  value={tenantId}
                  onValueChange={(value) => setTenantId(String(value))}
                >
                  <SelectTrigger id="impersonate-club" className="w-full">
                    <SelectValue>
                      {(value: string) => {
                        const match = active.find((m) => m.tenant_id === value)
                        return match
                          ? `${match.tenant_name} — ${roleLabel(tl, match.role)}`
                          : ""
                      }}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {active.map((membership) => (
                        <SelectItem
                          key={membership.tenant_id}
                          value={membership.tenant_id}
                        >
                          {membership.tenant_name} —{" "}
                          {roleLabel(tl, membership.role)}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="impersonate-reason">{t("reason")}</Label>
              <Textarea
                id="impersonate-reason"
                name="reason"
                required
                minLength={3}
                maxLength={500}
                placeholder={t("reasonPlaceholder")}
              />
              <p className="text-xs text-muted-foreground">{t("reasonHint")}</p>
            </div>

            {state && !state.success && (
              <p className="text-sm text-destructive">
                {t(`errors.${state.error}`)}
              </p>
            )}
          </DialogBody>

          <DialogFooter>
            <DialogClose
              render={
                <Button type="button" variant="outline">
                  {t("cancel")}
                </Button>
              }
            />
            <Button type="submit" disabled={pending}>
              {pending ? t("starting") : t("confirm")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
