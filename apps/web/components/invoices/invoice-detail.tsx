"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { toast } from "sonner"

import {
  cancelInvoiceAction,
  deleteInvoiceAction,
  markInvoicePaidAction,
  reopenInvoiceAction,
  updateInvoiceAction,
} from "@/actions/incoming-invoices"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { ConfirmAction } from "@/components/ui/confirm-action"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { formatDate } from "@/lib/time"
import type { IncomingInvoice } from "@/lib/types/incoming-invoices"
import { BanIcon, CheckIcon, DownloadIcon, RotateCcwIcon } from "lucide-react"

/** The fields a person may complete or correct. The file is not among them. */
const FIELDS = [
  "supplier_name",
  "supplier_vat_id",
  "invoice_number",
  "invoice_date",
  "due_date",
  "gross_amount",
  "net_amount",
  "tax_amount",
  "note",
] as const

type Field = (typeof FIELDS)[number]

function initial(invoice: IncomingInvoice): Record<Field, string> {
  return {
    supplier_name: invoice.supplier_name ?? "",
    supplier_vat_id: invoice.supplier_vat_id ?? "",
    invoice_number: invoice.invoice_number ?? "",
    invoice_date: invoice.invoice_date ?? "",
    due_date: invoice.due_date ?? "",
    gross_amount: invoice.gross_amount ?? "",
    net_amount: invoice.net_amount ?? "",
    tax_amount: invoice.tax_amount ?? "",
    note: invoice.note ?? "",
  }
}

/**
 * One invoice: what it says, and what the club has done about it.
 *
 * The figures are editable in place. There is no edit mode — the record is the
 * form, the same reading the member detail uses, and a save bar appears once
 * something differs from what is filed.
 */
export function InvoiceDetail({ invoice }: { invoice: IncomingInvoice }) {
  const t = useTranslations("invoices")
  const locale = useLocale()
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [draft, setDraft] = useState(() => initial(invoice))

  const filed = initial(invoice)
  const dirty = FIELDS.some((field) => draft[field] !== filed[field])

  function run(
    action: () => Promise<{ success: boolean; error?: string }>,
    message: string
  ) {
    startTransition(async () => {
      const result = await action()
      if (result.success) {
        toast.success(message)
        router.refresh()
      } else {
        toast.error(t(`errors.${result.error}`))
      }
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        {!invoice.is_complete && (
          <Badge variant="outline">{t("status.incomplete")}</Badge>
        )}
        {invoice.status === "paid" && (
          <Badge variant="secondary">
            {invoice.paid_on
              ? t("paidOn", {
                  date: formatDate(invoice.paid_on, locale, "UTC"),
                })
              : t("status.paid")}
          </Badge>
        )}
        {invoice.status === "cancelled" && (
          <Badge variant="outline">{t("status.cancelled")}</Badge>
        )}
        {invoice.source !== "manual" && (
          <Badge variant="secondary">{t("sources.electronic")}</Badge>
        )}

        <div className="ms-auto flex flex-wrap items-center gap-2">
          <a
            href={`/api/incoming-invoices/${invoice.id}/file`}
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            <DownloadIcon />
            {t("openFile")}
          </a>

          {invoice.status === "open" && (
            <Button
              size="sm"
              disabled={pending || invoice.gross_amount === null}
              // Disabled without an amount rather than hidden: the button is
              // where it is expected, and the reason is the empty field above.
              title={
                invoice.gross_amount === null ? t("payNeedsAmount") : undefined
              }
              onClick={() =>
                run(() => markInvoicePaidAction(invoice.id, null), t("paid"))
              }
            >
              <CheckIcon />
              {t("markPaid")}
            </Button>
          )}

          {invoice.status === "paid" && (
            <Button
              size="sm"
              variant="outline"
              disabled={pending}
              onClick={() =>
                run(() => reopenInvoiceAction(invoice.id), t("reopened"))
              }
            >
              <RotateCcwIcon />
              {t("reopen")}
            </Button>
          )}

          {invoice.status !== "cancelled" && (
            <ConfirmAction
              title={t("confirmCancel.title")}
              description={t("confirmCancel.description")}
              confirmLabel={t("cancelInvoice")}
              successMessage={t("cancelled")}
              variant="default"
              action={() => cancelInvoiceAction(invoice.id)}
              trigger={
                <Button size="sm" variant="outline" disabled={pending}>
                  <BanIcon />
                  {t("cancelInvoice")}
                </Button>
              }
            />
          )}

          <ConfirmAction
            title={t("confirmDelete.title")}
            description={t("confirmDelete.description")}
            confirmLabel={t("delete")}
            successMessage={t("deleted")}
            action={() => deleteInvoiceAction(invoice.id)}
            redirectTo="/incoming-invoices"
            trigger={
              <Button size="sm" variant="ghost" disabled={pending}>
                {t("delete")}
              </Button>
            }
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Text
          field="supplier_name"
          label={t("fields.supplier")}
          draft={draft}
          setDraft={setDraft}
        />
        <Text
          field="invoice_number"
          label={t("fields.number")}
          draft={draft}
          setDraft={setDraft}
        />
        <Text
          field="invoice_date"
          label={t("fields.date")}
          type="date"
          draft={draft}
          setDraft={setDraft}
        />
        <Text
          field="due_date"
          label={t("fields.due")}
          type="date"
          draft={draft}
          setDraft={setDraft}
        />
        <Text
          field="gross_amount"
          label={t("fields.gross")}
          inputMode="decimal"
          draft={draft}
          setDraft={setDraft}
        />
        <Text
          field="net_amount"
          label={t("fields.net")}
          inputMode="decimal"
          draft={draft}
          setDraft={setDraft}
        />
        <Text
          field="tax_amount"
          label={t("fields.tax")}
          inputMode="decimal"
          draft={draft}
          setDraft={setDraft}
        />
        <Text
          field="supplier_vat_id"
          label={t("fields.vatId")}
          draft={draft}
          setDraft={setDraft}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="note">{t("fields.note")}</Label>
        <Textarea
          id="note"
          rows={3}
          value={draft.note}
          onChange={(event) =>
            setDraft((current) => ({ ...current, note: event.target.value }))
          }
        />
      </div>

      {dirty && (
        <div className="flex items-center gap-2">
          <Button
            disabled={pending}
            onClick={() =>
              run(() => updateInvoiceAction(invoice.id, draft), t("saved"))
            }
          >
            {t("save")}
          </Button>
          <Button
            variant="ghost"
            disabled={pending}
            onClick={() => setDraft(initial(invoice))}
          >
            {t("discard")}
          </Button>
          {invoice.source !== "manual" && (
            // Said before saving, not after: the badge disappearing without
            // warning reads as the app losing track of where the figures came
            // from.
            <p className="text-sm text-muted-foreground">
              {t("editingLeavesElectronic")}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function Text({
  field,
  label,
  type,
  inputMode,
  draft,
  setDraft,
}: {
  field: Field
  label: string
  type?: string
  inputMode?: "decimal"
  draft: Record<Field, string>
  setDraft: (
    update: (current: Record<Field, string>) => Record<Field, string>
  ) => void
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={field}>{label}</Label>
      <Input
        id={field}
        type={type}
        inputMode={inputMode}
        value={draft[field]}
        onChange={(event) =>
          setDraft((current) => ({ ...current, [field]: event.target.value }))
        }
      />
    </div>
  )
}
