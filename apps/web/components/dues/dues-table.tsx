"use client"

import { useMemo, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useTranslations, useLocale } from "next-intl"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { DataTable } from "@/components/common/data-table"
import { buildDuesColumns } from "@/components/dues/dues-columns"
import { useCancelDue, useDues, usePayDue, useReopenDue } from "@/hooks/use-dues"
import { useErrorMessage } from "@/lib/errors"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  ArrowLeft01Icon,
  ArrowRight01Icon,
  MoreHorizontalIcon,
} from "@hugeicons/core-free-icons"
import type { Due } from "@/lib/types/due"

const CURRENT_YEAR = new Date().getFullYear()
const YEARS = Array.from({ length: 6 }, (_, i) => CURRENT_YEAR + 1 - i)

export function DuesTable() {
  const t = useTranslations("dues")
  const tc = useTranslations("common")
  const locale = useLocale()
  const router = useRouter()
  const searchParams = useSearchParams()
  const getErrorMessage = useErrorMessage()

  const page = Number(searchParams.get("page")) || 1
  const status = searchParams.get("status") || ""
  const year = Number(searchParams.get("year")) || CURRENT_YEAR

  const payDue = usePayDue()
  const cancelDue = useCancelDue()
  const reopenDue = useReopenDue()

  const { data, isLoading, error } = useDues({
    page,
    per_page: 20,
    status: status || undefined,
    year,
  })

  const [pendingId, setPendingId] = useState<string | null>(null)

  function updateParams(updates: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams.toString())
    Object.entries(updates).forEach(([key, value]) => {
      if (value === null || value === "") {
        params.delete(key)
      } else {
        params.set(key, value)
      }
    })
    if (!("page" in updates)) params.delete("page")
    router.replace(`/dues?${params.toString()}`, { scroll: false })
  }

  async function runAction(due: Due, action: "pay" | "cancel" | "reopen") {
    setPendingId(due.id)
    try {
      if (action === "pay") await payDue.mutateAsync({ id: due.id })
      if (action === "cancel") await cancelDue.mutateAsync(due.id)
      if (action === "reopen") await reopenDue.mutateAsync(due.id)
      toast.success(tc("saved"))
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setPendingId(null)
    }
  }

  const columns = useMemo(
    () =>
      buildDuesColumns({
        t,
        locale,
        actionsCell: ({ row }) => {
          const due = row.original
          return (
            <div onClick={(e) => e.stopPropagation()}>
              <DropdownMenu>
                <DropdownMenuTrigger
                  className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
                  disabled={pendingId === due.id}
                  aria-label={t("actions")}
                >
                  <HugeiconsIcon icon={MoreHorizontalIcon} size={16} />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {due.status === "open" && (
                    <>
                      <DropdownMenuItem onClick={() => runAction(due, "pay")}>
                        {t("markPaid")}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => runAction(due, "cancel")}>
                        {t("cancelDue")}
                      </DropdownMenuItem>
                    </>
                  )}
                  {due.status !== "open" && (
                    <DropdownMenuItem onClick={() => runAction(due, "reopen")}>
                      {t("reopenDue")}
                    </DropdownMenuItem>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          )
        },
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [locale, pendingId],
  )

  const dues = data?.data || []
  const meta = data?.meta

  const statusItems = [
    { value: "all", label: t("allStatuses") },
    { value: "open", label: t("status_open") },
    { value: "paid", label: t("status_paid") },
    { value: "cancelled", label: t("status_cancelled") },
  ]
  const yearItems = YEARS.map((y) => ({ value: String(y), label: String(y) }))

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Select
          items={yearItems}
          value={String(year)}
          onValueChange={(v) => updateParams({ year: v })}
        >
          <SelectTrigger className="w-28">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {yearItems.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          items={statusItems}
          value={status || "all"}
          onValueChange={(v) => updateParams({ status: v === "all" ? null : v })}
        >
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {statusItems.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <DataTable<Due>
        columns={columns}
        data={dues}
        isLoading={isLoading}
        error={error ?? null}
        errorStateText={tc("error")}
        getRowId={(row) => row.id}
        emptyState={
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <p className="text-lg font-medium">{t("noDues")}</p>
            <p className="text-muted-foreground mt-1 text-sm">
              {t("noDuesDescription")}
            </p>
          </div>
        }
      />

      {meta && meta.total_pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-muted-foreground text-sm">
            {meta.total} {t("title").toLowerCase()}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="icon-sm"
              disabled={page <= 1}
              onClick={() => updateParams({ page: String(page - 1) })}
              aria-label={tc("previous")}
            >
              <HugeiconsIcon icon={ArrowLeft01Icon} size={14} />
            </Button>
            <span className="flex items-center px-2 text-sm">
              {page} / {meta.total_pages}
            </span>
            <Button
              variant="outline"
              size="icon-sm"
              disabled={page >= meta.total_pages}
              onClick={() => updateParams({ page: String(page + 1) })}
              aria-label={tc("next")}
            >
              <HugeiconsIcon icon={ArrowRight01Icon} size={14} />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
