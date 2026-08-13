import { notFound } from "next/navigation"
import { DownloadIcon } from "lucide-react"
import { getLocale, getTranslations } from "next-intl/server"

import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"
import {
  AttendanceSection,
  DuesSection,
  ExpensesSection,
  MembershipSection,
} from "@/components/reports/report-sections"
import { YearPicker } from "@/components/reports/year-picker"
import { buttonVariants } from "@/components/ui/button"
import { getAnnualReport } from "@/lib/reports"

/**
 * The figures a club reads out once a year.
 *
 * Recomputed on every visit rather than stored: a saved report that disagrees
 * with the ledger is worse than a slow page, and there is nothing here a
 * treasurer would want frozen except the download.
 *
 * Board and above — the backend answers 403 for a member, which becomes
 * "this page does not exist" rather than a wall the nav walked them into.
 */
export default async function ReportsPage({
  searchParams,
}: {
  searchParams: Promise<{ year?: string }>
}) {
  const { year: requested } = await searchParams
  // Anything that is not four digits is simply no year: the backend then picks
  // the club's current one, which beats arguing with a hand-edited URL.
  const year = /^\d{4}$/.test(requested ?? "") ? Number(requested) : undefined

  const [t, locale, report] = await Promise.all([
    getTranslations("reports"),
    getLocale(),
    getAnnualReport(year).catch(() => null),
  ])
  if (report === null) notFound()

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <HeaderScrollTitle title={t("title")} />
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("title")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("description", { year: report.year })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <YearPicker year={report.year} years={report.years} />
          {/* A plain link, not an action: a download is a response with a
              file in it, and only a route handler can answer with one. */}
          <a
            href={`/api/reports/export?year=${report.year}`}
            className={buttonVariants({ variant: "outline" })}
          >
            <DownloadIcon />
            {t("download")}
          </a>
        </div>
      </div>

      <MembershipSection report={report.membership} />
      <DuesSection report={report.dues} locale={locale} />
      <ExpensesSection report={report.expenses} locale={locale} />
      <AttendanceSection report={report.attendance} locale={locale} />
    </>
  )
}
