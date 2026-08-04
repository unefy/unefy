"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { toast } from "sonner"

import { deleteRuleAction } from "@/actions/shooting"
import { RuleDialog } from "@/components/shooting/rule-dialog"
import { Button } from "@/components/ui/button"
import { DataTable, type DataTableColumn } from "@/components/ui/data-table"
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
import type { ShootingRule } from "@/lib/types/shooting"
import { Trash2Icon } from "lucide-react"

function DeleteRule({ rule }: { rule: ShootingRule }) {
  const t = useTranslations("shooting.rules.deleteDialog")
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [pending, startTransition] = useTransition()

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="ghost" size="sm" aria-label={t("action")}>
            <Trash2Icon className="text-destructive" />
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("title", { label: rule.label })}</DialogTitle>
          <DialogDescription>{t("description")}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose
            render={
              <Button type="button" variant="outline">
                {t("cancel")}
              </Button>
            }
          />
          <Button
            variant="destructive"
            disabled={pending}
            onClick={() =>
              startTransition(async () => {
                const result = await deleteRuleAction(rule.id)
                if (result.success) {
                  setOpen(false)
                  toast.success(t("deletedToast"))
                  router.refresh()
                } else {
                  toast.error(t(`errors.${result.error}`))
                }
              })
            }
          >
            {pending ? t("deleting") : t("action")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function RulesTable({
  rules,
  canEdit,
}: {
  rules: ShootingRule[]
  canEdit: boolean
}) {
  const t = useTranslations("shooting.rules")
  const locale = useLocale()

  const columns: DataTableColumn<ShootingRule>[] = [
    {
      key: "ruleKey",
      header: t("columns.ruleKey"),
      shrink: true,
      sortValue: (row) => row.rule_key,
      cellClassName: "font-mono text-xs",
      cell: (row) => row.rule_key,
    },
    {
      key: "label",
      header: t("columns.label"),
      sortValue: (row) => row.label,
      cell: (row) => <span className="font-medium">{row.label}</span>,
    },
    {
      key: "window",
      header: t("columns.window"),
      shrink: true,
      align: "center",
      cellClassName: "tabular-nums",
      cell: (row) => t("windowValue", { months: row.window_months }),
    },
    {
      key: "minDays",
      header: t("columns.minDays"),
      shrink: true,
      align: "center",
      cellClassName: "tabular-nums",
      cell: (row) => row.min_total_days ?? "—",
    },
    {
      key: "minMonths",
      header: t("columns.minMonths"),
      shrink: true,
      align: "center",
      cellClassName: "tabular-nums",
      cell: (row) => row.min_distinct_months ?? "—",
    },
  ]

  if (canEdit) {
    columns.push({
      key: "actions",
      header: "",
      shrink: true,
      cell: (row) => (
        <div className="flex justify-end gap-1">
          <RuleDialog rule={row} />
          <DeleteRule rule={row} />
        </div>
      ),
    })
  }

  return (
    <DataTable
      data={rules}
      columns={columns}
      rowKey={(row) => row.id}
      locale={locale}
      defaultSort={{ key: "ruleKey", direction: "asc" }}
      emptyText={t("empty")}
    />
  )
}
