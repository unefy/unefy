"use client"

import { useState, useTransition } from "react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import {
  inviteMemberAction,
  linkMemberAction,
  revokeInvitationAction,
  setAccessActiveAction,
  unlinkMemberAction,
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
  /** Club accounts not yet linked to any member — offered for linking. */
  availableAccounts?: ClubAccessMember[]
}

export function MemberAccess({
  member,
  access,
  invitation,
  availableAccounts = [],
}: MemberAccessProps) {
  const t = useTranslations("members.access")
  const tl = useTranslations("admin")
  const [pending, startTransition] = useTransition()
  const [open, setOpen] = useState(false)
  const [role, setRole] = useState("member")
  const [linkOpen, setLinkOpen] = useState(false)
  const [linkUserId, setLinkUserId] = useState("")
  /** Set after a successful invite — the one chance to copy the link. */
  const [inviteLink, setInviteLink] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const name = `${member.first_name} ${member.last_name}`

  function run(action: () => Promise<{ success: boolean; error?: string }>) {
    startTransition(async () => {
      const result = await action()
      if (result.success) {
        setOpen(false)
        setLinkOpen(false)
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
            <div className="ms-auto flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                disabled={pending}
                onClick={() => run(() => unlinkMemberAction(member.id))}
              >
                {t("unlink")}
              </Button>
              <Button
                variant="outline"
                size="sm"
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
            <Dialog
              open={open}
              onOpenChange={(next) => {
                setOpen(next)
                if (!next) {
                  setInviteLink(null)
                  setCopied(false)
                }
              }}
            >
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
                  {inviteLink ? (
                    <div className="space-y-2">
                      <Label htmlFor="invite-link">{t("linkReady")}</Label>
                      <div className="flex gap-2">
                        <input
                          id="invite-link"
                          readOnly
                          value={inviteLink}
                          className="w-full rounded-md border bg-muted px-2 py-1 font-mono text-xs"
                          onFocus={(event) => event.currentTarget.select()}
                        />
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={async () => {
                            await navigator.clipboard.writeText(inviteLink)
                            setCopied(true)
                          }}
                        >
                          {copied ? t("copied") : t("copy")}
                        </Button>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {t("linkReadyHint")}
                      </p>
                    </div>
                  ) : (
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
                  )}
                </DialogBody>

                <DialogFooter>
                  <DialogClose
                    render={
                      <Button type="button" variant="outline">
                        {inviteLink ? t("close") : t("cancel")}
                      </Button>
                    }
                  />
                  {!inviteLink && (
                    <Button
                      disabled={pending}
                      onClick={() =>
                        startTransition(async () => {
                          const result = await inviteMemberAction(
                            member.id,
                            role
                          )
                          if (result.success) {
                            // Keep the dialog open: this response is the only
                            // carrier of the link, closing would discard it.
                            setInviteLink(result.data?.accept_url ?? null)
                          } else {
                            toast.error(
                              t(`errors.${result.error ?? "unknown"}`)
                            )
                          }
                        })
                      }
                    >
                      {pending ? t("inviting") : t("invite")}
                    </Button>
                  )}
                </DialogFooter>
              </DialogContent>
            </Dialog>
            {/* The other direction: the person already signed in (founder,
                Google login) and only the binding to the register is missing.
                An invitation cannot reach them — the backend refuses addresses
                that already have access. */}
            {availableAccounts.length > 0 && (
              <Dialog open={linkOpen} onOpenChange={setLinkOpen}>
                <DialogTrigger
                  render={
                    <Button variant="outline" size="sm" disabled={pending}>
                      {t("link")}
                    </Button>
                  }
                />
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>{t("linkTitle")}</DialogTitle>
                    <DialogDescription>
                      {t("linkDescription", { name })}
                    </DialogDescription>
                  </DialogHeader>

                  <DialogBody>
                    <div className="space-y-2">
                      <Label htmlFor="link-account">{t("account")}</Label>
                      <Select
                        value={linkUserId}
                        onValueChange={(value) => setLinkUserId(String(value))}
                      >
                        <SelectTrigger id="link-account" className="w-full">
                          <SelectValue>
                            {(value: string) => {
                              const account = availableAccounts.find(
                                (a) => a.user_id === value
                              )
                              return account
                                ? `${account.name} (${account.email})`
                                : t("pickAccount")
                            }}
                          </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                          <SelectGroup>
                            {availableAccounts.map((account) => (
                              <SelectItem
                                key={account.user_id}
                                value={account.user_id}
                              >
                                {account.name} ({account.email})
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
                      disabled={pending || !linkUserId}
                      onClick={() =>
                        run(() => linkMemberAction(member.id, linkUserId))
                      }
                    >
                      {pending ? t("linking") : t("link")}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
