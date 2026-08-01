"use client"

import { useActionState, useState } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { setAccessActiveAction } from "@/actions/club-access"
import {
  createMemberAction,
  updateMemberAction,
  type ActionResult,
} from "@/actions/members"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
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
import { MEMBER_STATUS_KEYS, memberStatusLabel } from "@/lib/labels"
import type { Member } from "@/lib/types/member"
import { PencilIcon, PlusIcon } from "lucide-react"

/** Statuses that end the membership — see `MEMBER_STATUS_KEYS`. */
const LEAVING_STATUSES = ["resigned", "terminated", "deceased"]

type MemberDialogProps = {
  /** Omitted when creating. */
  member?: Member
  /** The member's account, so leaving can offer to block it in one step. */
  hasActiveAccount?: boolean
  accountUserId?: string
}

function Field({
  id,
  label,
  children,
}: {
  id: string
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  )
}

export function MemberDialog({
  member,
  hasActiveAccount = false,
  accountUserId,
}: MemberDialogProps) {
  const t = useTranslations("members.form")
  const tl = useTranslations("admin")
  const router = useRouter()
  const isEdit = member !== undefined

  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState(member?.status ?? "active")
  const [blockAccess, setBlockAccess] = useState(true)

  // The member is leaving and still has a working account — the one moment
  // where access should usually be withdrawn, so it is offered right here
  // instead of being a separate errand on another page.
  const offerBlock =
    isEdit &&
    hasActiveAccount &&
    LEAVING_STATUSES.includes(status) &&
    !LEAVING_STATUSES.includes(member.status)

  // Side effects live inside the action rather than in an effect watching its
  // result: an effect would fire again on every unrelated re-render and would
  // have to guard against repeating the toast.
  const [, formAction, pending] = useActionState<
    ActionResult | undefined,
    FormData
  >(async (prev, formData) => {
    const submit = isEdit
      ? updateMemberAction.bind(null, member.id)
      : createMemberAction
    const result = await submit(prev, formData)

    if (result.success) {
      setOpen(false)
      toast.success(isEdit ? t("savedToast") : t("createdToast"))
      if (offerBlock && blockAccess && accountUserId) {
        await setAccessActiveAction(accountUserId, false, member.id)
      }
      router.refresh()
    } else {
      toast.error(t(`errors.${result.error}`))
    }
    return result
  }, undefined)

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          isEdit ? (
            <Button variant="outline" size="sm">
              <PencilIcon />
              {t("edit")}
            </Button>
          ) : (
            <Button size="sm">
              <PlusIcon />
              {t("create")}
            </Button>
          )
        }
      />
      <DialogContent className="sm:max-w-2xl">
        <form action={formAction}>
          <DialogHeader>
            <DialogTitle>
              {isEdit ? t("editTitle") : t("createTitle")}
            </DialogTitle>
            <DialogDescription>{t("sections.person")}</DialogDescription>
          </DialogHeader>

          <DialogBody>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field id="first_name" label={t("fields.firstName")}>
                <Input
                  id="first_name"
                  name="first_name"
                  defaultValue={member?.first_name ?? ""}
                  required
                />
              </Field>
              <Field id="last_name" label={t("fields.lastName")}>
                <Input
                  id="last_name"
                  name="last_name"
                  defaultValue={member?.last_name ?? ""}
                  required
                />
              </Field>
              <Field id="birthday" label={t("fields.birthday")}>
                <Input
                  id="birthday"
                  name="birthday"
                  type="date"
                  defaultValue={member?.birthday ?? ""}
                />
              </Field>
              <Field id="category" label={t("fields.category")}>
                <Input
                  id="category"
                  name="category"
                  defaultValue={member?.category ?? ""}
                />
              </Field>
            </div>

            <h3 className="pt-2 text-sm font-medium">
              {t("sections.contact")}
            </h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field id="email" label={t("fields.email")}>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  defaultValue={member?.email ?? ""}
                />
              </Field>
              <Field id="phone" label={t("fields.phone")}>
                <Input
                  id="phone"
                  name="phone"
                  defaultValue={member?.phone ?? ""}
                />
              </Field>
              <Field id="mobile" label={t("fields.mobile")}>
                <Input
                  id="mobile"
                  name="mobile"
                  defaultValue={member?.mobile ?? ""}
                />
              </Field>
            </div>

            <h3 className="pt-2 text-sm font-medium">
              {t("sections.address")}
            </h3>
            <div className="grid gap-3 sm:grid-cols-4">
              <Field id="street" label={t("fields.street")}>
                <Input
                  id="street"
                  name="street"
                  defaultValue={member?.street ?? ""}
                  className="sm:col-span-2"
                />
              </Field>
              <Field id="zip_code" label={t("fields.zipCode")}>
                <Input
                  id="zip_code"
                  name="zip_code"
                  defaultValue={member?.zip_code ?? ""}
                />
              </Field>
              <Field id="city" label={t("fields.city")}>
                <Input
                  id="city"
                  name="city"
                  defaultValue={member?.city ?? ""}
                />
              </Field>
              <Field id="country" label={t("fields.country")}>
                <Input
                  id="country"
                  name="country"
                  defaultValue={member?.country ?? ""}
                />
              </Field>
            </div>

            <h3 className="pt-2 text-sm font-medium">
              {t("sections.membership")}
            </h3>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field id="status" label={t("fields.status")}>
                {/* The value travels in a hidden input: the shadcn Select is a
                    button, not a form control, so it submits nothing itself. */}
                <input type="hidden" name="status" value={status} />
                <Select
                  value={status}
                  onValueChange={(value) => setStatus(String(value))}
                >
                  <SelectTrigger id="status" className="w-full">
                    <SelectValue>
                      {(value: string) => memberStatusLabel(tl, value)}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {MEMBER_STATUS_KEYS.map((key) => (
                        <SelectItem key={key} value={key}>
                          {memberStatusLabel(tl, key)}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
              <Field id="joined_at" label={t("fields.joinedAt")}>
                <Input
                  id="joined_at"
                  name="joined_at"
                  type="date"
                  defaultValue={member?.joined_at ?? ""}
                />
              </Field>
              {isEdit && (
                <Field id="left_at" label={t("fields.leftAt")}>
                  <Input
                    id="left_at"
                    name="left_at"
                    type="date"
                    defaultValue={member?.left_at ?? ""}
                  />
                </Field>
              )}
            </div>

            {offerBlock && (
              <label className="flex items-start gap-2 rounded-md border p-3 text-sm">
                <Checkbox
                  checked={blockAccess}
                  onCheckedChange={(checked) =>
                    setBlockAccess(checked === true)
                  }
                />
                <span>
                  {t("blockAccess")}
                  <span className="block text-xs text-muted-foreground">
                    {t("blockAccessHint")}
                  </span>
                </span>
              </label>
            )}

            <h3 className="pt-2 text-sm font-medium">
              {t("sections.banking")}
            </h3>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field id="iban" label={t("fields.iban")}>
                <Input
                  id="iban"
                  name="iban"
                  defaultValue={member?.iban ?? ""}
                />
              </Field>
              <Field id="bic" label={t("fields.bic")}>
                <Input id="bic" name="bic" defaultValue={member?.bic ?? ""} />
              </Field>
              <Field id="account_holder" label={t("fields.accountHolder")}>
                <Input
                  id="account_holder"
                  name="account_holder"
                  defaultValue={member?.account_holder ?? ""}
                />
              </Field>
            </div>

            <Field id="notes" label={t("fields.notes")}>
              <Textarea
                id="notes"
                name="notes"
                defaultValue={member?.notes ?? ""}
              />
            </Field>
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
              {pending ? t("saving") : t("save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
