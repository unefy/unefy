import Link from "next/link"
import { getLocale, getTranslations } from "next-intl/server"

import { DuesTable } from "@/components/dues/dues-table"
import { DuesToolbar } from "@/components/dues/dues-toolbar"
import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { getClubTimeZone } from "@/lib/attendance"
import { getClub } from "@/lib/club"
import { getDuesSummary, listAllDues } from "@/lib/dues"
import { ReceiptIcon } from "lucide-react"

function euro(amount: string, locale: string): string {
  return Number(amount).toLocaleString(locale, {
    style: "currency",
    currency: "EUR",
  })
}

/** The club's own today, not the browser's — see `lib/time`. */
function clubToday(timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone }).format(new Date())
}

export default async function DuesPage() {
  const [t, locale, timeZone] = await Promise.all([
    getTranslations("dues"),
    getLocale(),
    getClubTimeZone(),
  ])

  // Each read fails soft: the book must still render when the summary or the
  // club record hiccups.
  const [dues, summary, club] = await Promise.all([
    listAllDues().catch(() => ({ data: [], total: 0, truncated: false })),
    getDuesSummary().catch(() => null),
    getClub().catch(() => null),
  ])

  const today = clubToday(timeZone)
  const sepaReady = Boolean(club?.sepa_creditor_id && club?.iban)

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <HeaderScrollTitle title={t("title")} />
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("title")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("description", { count: dues.total })}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            render={
              <Link href="/dues/fee-types">
                <ReceiptIcon />
                {t("feeTypes.title")}
              </Link>
            }
          />
          <DuesToolbar
            currentYear={Number(today.slice(0, 4))}
            sepaReady={sepaReady}
          />
        </div>
      </div>

      {summary && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Card>
            <CardHeader>
              <CardDescription>{t("summary.open")}</CardDescription>
              <CardTitle className="text-2xl tabular-nums">
                {euro(summary.open_amount, locale)}
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                {t("summary.count", { count: summary.open_count })}
              </p>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>{t("summary.paid")}</CardDescription>
              <CardTitle className="text-2xl tabular-nums">
                {euro(summary.paid_amount, locale)}
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                {t("summary.count", { count: summary.paid_count })}
              </p>
            </CardHeader>
          </Card>
        </div>
      )}

      {dues.truncated && (
        <p className="text-sm text-destructive">
          {t("truncated", { shown: dues.data.length })}
        </p>
      )}
      <DuesTable
        dues={dues.data}
        timeZone={timeZone}
        today={today}
        canManage
        showMember
      />
    </>
  )
}
