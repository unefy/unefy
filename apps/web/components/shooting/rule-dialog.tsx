"use client"

import { useActionState, useState } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import {
  createRuleAction,
  updateRuleAction,
  type ActionResult,
} from "@/actions/shooting"
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { ShootingRule } from "@/lib/types/shooting"
import { PencilIcon, PlusIcon } from "lucide-react"

function Field({
  id,
  label,
  hint,
  children,
}: {
  id: string
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

export function RuleDialog({ rule }: { rule?: ShootingRule }) {
  const t = useTranslations("shooting.rules.form")
  const router = useRouter()
  const isEdit = rule !== undefined

  const [open, setOpen] = useState(false)

  const [, formAction, pending] = useActionState<
    ActionResult | undefined,
    FormData
  >(async (prev, formData) => {
    const submit = isEdit
      ? updateRuleAction.bind(null, rule.id)
      : createRuleAction
    const result = await submit(prev, formData)

    if (result.success) {
      setOpen(false)
      toast.success(isEdit ? t("savedToast") : t("createdToast"))
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
        <form action={formAction}>
          <DialogHeader>
            <DialogTitle>
              {isEdit ? t("editTitle") : t("createTitle")}
            </DialogTitle>
            <DialogDescription>{t("intro")}</DialogDescription>
          </DialogHeader>

          <DialogBody>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field
                id="rule_key"
                label={t("fields.ruleKey")}
                hint={t("fields.ruleKeyHint")}
              >
                {/* Frozen after creation: issued certificates carry the key,
                    and renaming it would orphan what they reference. The
                    disabled input still submits nothing, so the value rides
                    in a hidden field for the schema's sake. */}
                {isEdit && (
                  <input type="hidden" name="rule_key" value={rule.rule_key} />
                )}
                <Input
                  id="rule_key"
                  name={isEdit ? undefined : "rule_key"}
                  defaultValue={rule?.rule_key ?? ""}
                  disabled={isEdit}
                  required
                  pattern="[a-z0-9_-]+"
                />
              </Field>
              <Field id="label" label={t("fields.label")}>
                <Input
                  id="label"
                  name="label"
                  defaultValue={rule?.label ?? ""}
                  required
                />
              </Field>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <Field id="window_months" label={t("fields.windowMonths")}>
                <Input
                  id="window_months"
                  name="window_months"
                  type="number"
                  min={1}
                  max={60}
                  defaultValue={rule?.window_months ?? 12}
                  required
                />
              </Field>
              <Field
                id="min_total_days"
                label={t("fields.minTotalDays")}
                hint={t("fields.minTotalDaysHint")}
              >
                <Input
                  id="min_total_days"
                  name="min_total_days"
                  type="number"
                  min={1}
                  defaultValue={rule?.min_total_days ?? ""}
                />
              </Field>
              <Field
                id="min_distinct_months"
                label={t("fields.minDistinctMonths")}
                hint={t("fields.minDistinctMonthsHint")}
              >
                <Input
                  id="min_distinct_months"
                  name="min_distinct_months"
                  type="number"
                  min={1}
                  defaultValue={rule?.min_distinct_months ?? ""}
                />
              </Field>
            </div>

            <p className="text-xs text-muted-foreground">{t("criteriaHint")}</p>
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
