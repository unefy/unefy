import { notFound } from "next/navigation"
import { getLocale, getTranslations } from "next-intl/server"

import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"
import { InvoiceUpload } from "@/components/invoices/invoice-upload"
import { InvoicesTable } from "@/components/invoices/invoices-table"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { getClubTimeZone } from "@/lib/attendance"
import {
  getIncomingInvoiceSummary,
  listIncomingInvoices,
} from "@/lib/incoming-invoices"

/** The club's own today, not the browser's — see the dues page. */
function clubToday(timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone }).format(new Date())
}

function euro(amount: string, locale: string): string {
  return Number(amount).toLocaleString(locale, {
    style: "currency",
    currency: "EUR",
  })
}

function Stat({
  label,
  value,
  hint,
}: {
  label: string
  value: string
  hint?: string
}) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-2xl tabular-nums">{value}</CardTitle>
      </CardHeader>
      {hint && (
        <CardContent className="text-sm text-muted-foreground">
          {hint}
        </CardContent>
      )}
    </Card>
  )
}

/**
 * The invoices the club has received.
 *
 * A register: what arrived, from whom, for how much, and whether it is paid.
 * Board and above — the backend refuses the endpoint for anyone else, and this
 * page turns that into "does not exist" rather than a wall the nav walked
 * somebody into.
 */
export default async function IncomingInvoicesPage() {
  const [t, locale, timeZone, listed, summary] = await Promise.all([
    getTranslations("invoices"),
    getLocale(),
    getClubTimeZone(),
    listIncomingInvoices().catch(() => null),
    getIncomingInvoiceSummary().catch(() => null),
  ])
  if (listed === null || summary === null) notFound()

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <HeaderScrollTitle title={t("title")} />
          <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">
            {t("description", { count: listed.meta.total })}
          </p>
        </div>
        <InvoiceUpload />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Stat
          label={t("summary.open")}
          value={euro(summary.open_amount, locale)}
          hint={t("summary.openCount", { count: summary.open_count })}
        />
        <Stat
          label={t("summary.paid")}
          value={euro(summary.paid_amount, locale)}
          hint={t("summary.paidCount", { count: summary.paid_count })}
        />
        <Stat
          label={t("summary.total")}
          value={euro(summary.total_amount, locale)}
          // Said on the tile rather than left to be discovered: a total that
          // silently omits four untyped scans is a wrong total.
          hint={
            summary.incomplete_count > 0
              ? t("summary.incomplete", { count: summary.incomplete_count })
              : undefined
          }
        />
      </div>

      <InvoicesTable
        invoices={listed.data}
        timeZone={timeZone}
        today={clubToday(timeZone)}
      />
    </>
  )
}
