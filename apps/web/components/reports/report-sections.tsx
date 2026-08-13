import { getTranslations } from "next-intl/server"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { genderLabel } from "@/lib/labels"
import type {
  AttendanceReport,
  CountByValue,
  DuesReport,
  ExpensesReport,
  MembershipReport,
} from "@/lib/types/reports"

function euro(amount: string, locale: string): string {
  return Number(amount).toLocaleString(locale, {
    style: "currency",
    currency: "EUR",
  })
}

/**
 * One headline number.
 *
 * The delta is the year's net movement against the opening balance, named
 * rather than implied — "+3 gegenüber Jahresanfang" is a sentence a treasurer
 * can read out; a bare green arrow is not.
 */
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
 * A breakdown, with a row for the records that carry no value.
 *
 * The nameless row is shown rather than dropped: "37 members, of which 12 have
 * no category" is a fact about the club's records, and hiding it makes the
 * column quietly fail to add up to the membership above.
 */
function BreakdownTable({
  title,
  rows,
  emptyLabel,
  labelFor,
}: {
  title: string
  rows: CountByValue[]
  emptyLabel: string
  labelFor?: (value: string) => string
}) {
  if (rows.length === 0) return null
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium">{title}</h3>
      <Table>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.value ?? "__none__"}>
              <TableCell
                className={
                  row.value === null ? "text-muted-foreground" : undefined
                }
              >
                {row.value === null
                  ? emptyLabel
                  : (labelFor?.(row.value) ?? row.value)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {row.count}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

export async function MembershipSection({
  report,
}: {
  report: MembershipReport
}) {
  const t = await getTranslations("reports")
  // The gender labels already exist under `admin`; a second set of the same
  // three words would only be a second chance to disagree with the first.
  const admin = await getTranslations("admin")
  const net = report.closing - report.opening

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-medium">{t("membership.title")}</h2>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label={t("membership.opening")} value={String(report.opening)} />
        <Stat label={t("membership.joined")} value={`+${report.joined}`} />
        <Stat label={t("membership.left")} value={`−${report.left}`} />
        <Stat
          label={t("membership.closing")}
          value={String(report.closing)}
          hint={t("membership.net", {
            net: net > 0 ? `+${net}` : String(net),
          })}
        />
      </div>

      <p className="text-sm text-muted-foreground">
        {t("membership.balanceNote")}
      </p>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <BreakdownTable
          title={t("membership.byCategory")}
          rows={report.by_category}
          emptyLabel={t("noValue")}
        />
        <BreakdownTable
          title={t("membership.byGender")}
          rows={report.by_gender}
          emptyLabel={t("noValue")}
          labelFor={(value) => genderLabel(admin, value)}
        />
        <div className="space-y-2">
          <h3 className="text-sm font-medium">{t("membership.byAge")}</h3>
          <Table>
            <TableBody>
              {report.by_age_band.map((row) => (
                <TableRow key={row.band}>
                  <TableCell>{t(`ageBands.${row.band}`)}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {row.count}
                  </TableCell>
                </TableRow>
              ))}
              {report.without_birthday > 0 && (
                <TableRow>
                  <TableCell className="text-muted-foreground">
                    {t("membership.withoutBirthday")}
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground tabular-nums">
                    {report.without_birthday}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      {report.without_leaving_date > 0 && (
        // A figure the club can act on, not a warning it can only look at: the
        // count is stated because these members still count as present above.
        <p className="text-sm text-muted-foreground">
          {t("membership.withoutLeavingDate", {
            count: report.without_leaving_date,
          })}
        </p>
      )}
    </section>
  )
}

export async function DuesSection({
  report,
  locale,
}: {
  report: DuesReport
  locale: string
}) {
  const t = await getTranslations("reports")

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-medium">{t("dues.title")}</h2>

      {report.by_fee.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("dues.empty")}</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("dues.feeName")}</TableHead>
              <TableHead className="text-right">{t("dues.count")}</TableHead>
              <TableHead className="text-right">{t("dues.charged")}</TableHead>
              <TableHead className="text-right">{t("dues.paid")}</TableHead>
              <TableHead className="text-right">{t("dues.open")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {report.by_fee.map((row) => (
              <TableRow key={row.fee_name}>
                <TableCell>{row.fee_name}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {row.count}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {euro(row.charged, locale)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {euro(row.paid, locale)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {euro(row.open, locale)}
                </TableCell>
              </TableRow>
            ))}
            <TableRow className="font-medium">
              <TableCell>{t("dues.total")}</TableCell>
              <TableCell className="text-right tabular-nums">
                {report.totals.count}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {euro(report.totals.charged, locale)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {euro(report.totals.paid, locale)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {euro(report.totals.open, locale)}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      )}

      {report.totals.cancelled_count > 0 && (
        // Beside the table rather than inside it: a cancelled charge was never
        // owed, so it belongs in neither Soll nor Offen — but the decision to
        // cancel it should not vanish either.
        <p className="text-sm text-muted-foreground">
          {t("dues.cancelled", {
            count: report.totals.cancelled_count,
            amount: euro(report.totals.cancelled, locale),
          })}
        </p>
      )}
    </section>
  )
}

export async function ExpensesSection({
  report,
  locale,
}: {
  report: ExpensesReport
  locale: string
}) {
  const t = await getTranslations("reports")

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-medium">{t("expenses.title")}</h2>

      {report.by_supplier.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("expenses.empty")}</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("expenses.supplier")}</TableHead>
              <TableHead className="text-right">
                {t("expenses.count")}
              </TableHead>
              <TableHead className="text-right">
                {t("expenses.total")}
              </TableHead>
              <TableHead className="text-right">{t("expenses.open")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {report.by_supplier.map((row) => (
              <TableRow key={row.supplier_name ?? "__none__"}>
                <TableCell
                  className={
                    row.supplier_name === null
                      ? "text-muted-foreground"
                      : undefined
                  }
                >
                  {row.supplier_name ?? t("noValue")}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {row.count}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {euro(row.total, locale)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {Number(row.open) > 0 ? euro(row.open, locale) : "—"}
                </TableCell>
              </TableRow>
            ))}
            <TableRow className="font-medium">
              <TableCell>{t("expenses.sum")}</TableCell>
              <TableCell className="text-right tabular-nums">
                {report.count}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {euro(report.total, locale)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {Number(report.open) > 0 ? euro(report.open, locale) : "—"}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      )}

      {report.incomplete_count > 0 && (
        // The rows the total cannot see. Stated here rather than only on the
        // register, because this is the figure that gets read out.
        <p className="text-sm text-muted-foreground">
          {t("expenses.incomplete", { count: report.incomplete_count })}
        </p>
      )}
    </section>
  )
}

export async function AttendanceSection({
  report,
  locale,
}: {
  report: AttendanceReport
  locale: string
}) {
  const t = await getTranslations("reports")
  const busiest = Math.max(...report.by_month.map((m) => m.count), 0)

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-medium">{t("attendance.title")}</h2>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label={t("attendance.sessions")}
          value={String(report.sessions)}
        />
        <Stat
          label={t("attendance.records")}
          value={String(report.records)}
          hint={
            report.guests > 0
              ? t("attendance.guests", { count: report.guests })
              : undefined
          }
        />
        <Stat label={t("attendance.members")} value={String(report.members)} />
        <Stat
          label={t("attendance.average")}
          // Null rather than 0.0 when nothing was held: "0.0 per evening"
          // reads as a turnout problem instead of an empty year.
          value={
            report.average_per_session === null
              ? "—"
              : report.average_per_session.toLocaleString(locale, {
                  minimumFractionDigits: 1,
                  maximumFractionDigits: 1,
                })
          }
          hint={
            report.self_kept > 0
              ? t("attendance.selfKept", { count: report.self_kept })
              : undefined
          }
        />
      </div>

      {/*
        A table with a bar in it, not a chart. Every month's figure goes into
        the report, so the numbers are a column and read exactly; the bar is
        only there so the season is visible without reading twelve rows. One
        series, so no legend and no palette — the bar wears the text colour at
        low opacity and carries no meaning the number does not.
      */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("attendance.month")}</TableHead>
            <TableHead className="text-right">
              {t("attendance.visits")}
            </TableHead>
            <TableHead className="w-1/2" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {report.by_month.map((row) => (
            <TableRow key={row.month}>
              <TableCell>{t(`months.${row.month}`)}</TableCell>
              <TableCell className="text-right tabular-nums">
                {row.count}
              </TableCell>
              <TableCell>
                <div
                  aria-hidden
                  className="h-2 rounded-r-[4px] bg-foreground/25"
                  style={{
                    width: busiest > 0 ? `${(row.count / busiest) * 100}%` : 0,
                  }}
                />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  )
}
