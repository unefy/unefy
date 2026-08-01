"use client"

import { useState, useTransition } from "react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import {
  inviteMemberAction,
  revokeInvitationAction,
  setAccessActiveAction,
} from "@/actions/club-access"
import { Badge } from "@/components/ui/badge"
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
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { DateCell } from "@/components/ui/date-cell"
import { ROLE_KEYS, roleLabel } from "@/lib/labels"
import type {
  ClubAccessMember,
  ClubInvitation,
  Member,
} from "@/lib/types/member"

type MemberAccessProps = {
  member: Member
  /** The account linked to this member, if the invitation was accepted. */
  access: ClubAccessMember | null
  /** An invitation for this member that is still open. */
  invitation: ClubInvitation | null
}

export function MemberAccess({
  member,
  access,
  invitation,
}: MemberAccessProps) {
  const t = useTranslations("members.access")
  const tl = useTranslations("admin")
  const [pending, startTransition] = useTransition()
  const [open, setOpen] = useState(false)
  const [role, setRole] = useState("member")

  const name = `${member.first_name} ${member.last_name}`

  function run(action: () => Promise<{ success: boolean; error?: string }>) {
    startTransition(async () => {
      const result = await action()
      if (result.success) {
        setOpen(false)
      } else {
        toast.error(t(`errors.${result.error ?? "unknown"}`))
      }
    })
  }

  return (
    <section className="space-y-3">
      <div className="space-y-1">
        <h2 className="text-sm font-medium text-muted-foreground">
          {t("title")}
        </h2>
        <p className="text-xs text-muted-foreground">{t("hint")}</p>
      </div>

      <div className="rounded-md border p-4">
        {access ? (
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm">
              {t("active", { email: access.email })}
            </span>
            <Badge variant="outline">{roleLabel(tl, access.role)}</Badge>
            {!access.is_active && (
              <Badge variant="destructive">{t("blocked")}</Badge>
            )}
            <Button
              variant="outline"
              size="sm"
              className="ms-auto"
              disabled={pending}
              onClick={() =>
                run(() =>
                  setAccessActiveAction(
                    access.user_id,
                    !access.is_active,
                    member.id
                  )
                )
              }
            >
              {access.is_active ? t("block") : t("unblock")}
            </Button>
          </div>
        ) : invitation ? (
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm">
              {t("pending", { email: invitation.email })}{" "}
              <DateCell value={invitation.expires_at} dateOnly />
            </span>
            <Badge variant="outline">{roleLabel(tl, invitation.role)}</Badge>
            <Button
              variant="outline"
              size="sm"
              className="ms-auto"
              disabled={pending}
              onClick={() =>
                run(() => revokeInvitationAction(invitation.id, member.id))
              }
            >
              {t("revokeInvite")}
            </Button>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm text-muted-foreground">
              {member.email ? t("none") : t("noEmail")}
            </span>
            {/* Without an address in the record there is nothing to invite to,
                and the backend would refuse — so the control stays disabled
                rather than offering an action that cannot succeed. */}
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger
                render={
                  <Button
                    size="sm"
                    className="ms-auto"
                    disabled={!member.email || pending}
                  >
                    {t("invite")}
                  </Button>
                }
              />
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>{t("inviteTitle")}</DialogTitle>
                  <DialogDescription>
                    {t("inviteDescription", {
                      name,
                      email: member.email ?? "",
                    })}
                  </DialogDescription>
                </DialogHeader>

                <DialogBody>
                  <div className="space-y-2">
                    <Label htmlFor="invite-role">{t("role")}</Label>
                    <Select
                      value={role}
                      onValueChange={(value) => setRole(String(value))}
                    >
                      <SelectTrigger id="invite-role" className="w-full">
                        <SelectValue>
                          {(value: string) => roleLabel(tl, value)}
                        </SelectValue>
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          {ROLE_KEYS.map((key) => (
                            <SelectItem key={key} value={key}>
                              {roleLabel(tl, key)}
                            </SelectItem>
                          ))}
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </div>
                </DialogBody>

                <DialogFooter>
                  <DialogClose
                    render={
                      <Button type="button" variant="outline">
                        {t("cancel")}
                      </Button>
                    }
                  />
                  <Button
                    disabled={pending}
                    onClick={() =>
                      run(() => inviteMemberAction(member.id, role))
                    }
                  >
                    {pending ? t("inviting") : t("invite")}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        )}
      </div>
    </section>
  )
}
