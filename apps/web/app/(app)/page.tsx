import Link from "next/link"
import { getLocale, getTranslations } from "next-intl/server"

import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { getClubTimeZone, listAttendanceSessions } from "@/lib/attendance"
import { getSession } from "@/lib/auth"
import { getDuesSummary, listMyDues } from "@/lib/dues"
import { getMemberStatusCounts } from "@/lib/members"
import { formatDateTime } from "@/lib/time"

const BOARD_ROLES = ["owner", "admin", "board"]

/** How many open sessions the board card lists before it stops. */
const OPEN_SESSION_LIMIT = 5

function formatEuro(amount: string, locale: string): string {
  return Number(amount).toLocaleString(locale, {
    style: "currency",
    currency: "EUR",
  })
}

function Stat({
  label,
  value,
  hint,
  href,
}: {
  label: string
  value: string
  hint?: string
  href?: string
}) {
  const card = (
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
  return href ? (
    <Link href={href} className="block rounded-xl outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50">
      {card}
    </Link>
  ) : (
    card
  )
}

/**
 * The club's front page, and the redirect target after every login.
 *
 * Reads are role-aware and each one fails soft: a board-only endpoint answers
 * 403 for a plain member, and a card that cannot be filled is left out rather
 * than taking the page down with it.
 */
export default async function DashboardPage() {
  const [t, locale, session] = await Promise.all([
    getTranslations("dashboard"),
    getLocale(),
    getSession(),
  ])

  const isBoard = BOARD_ROLES.includes(session?.role ?? "")

  const [members, dues, openSessions, timeZone, myDues] = await Promise.all([
    isBoard ? getMemberStatusCounts().catch(() => null) : null,
    isBoard ? getDuesSummary().catch(() => null) : null,
    isBoard
      ? listAttendanceSessions({ status: "open", perPage: OPEN_SESSION_LIMIT })
          .then((r) => r)
          .catch(() => null)
      : null,
    getClubTimeZone(),
    isBoard ? [] : listMyDues().catch(() => []),
  ])

  const openMyDues = myDues.filter((due) => due.status === "open")

  return (
    <>
      <div className="space-y-1">
        <HeaderScrollTitle title={t("title")} />
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">
          {session?.tenant_name
            ? t("subtitleClub", { club: session.tenant_name })
            : t("subtitle")}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {members && (
          <Stat
            label={t("stats.members")}
            value={String(members.total)}
            hint={t("stats.membersActive", {
              count: members.counts.active ?? 0,
            })}
            href="/members"
          />
        )}
        {dues && (
          <Stat
            label={t("stats.duesOpen")}
            value={formatEuro(dues.open_amount, locale)}
            hint={t("stats.duesOpenCount", { count: dues.open_count })}
          />
        )}
        {openSessions && (
          <Stat
            label={t("stats.openSessions")}
            value={String(openSessions.meta.total)}
            hint={t("stats.openSessionsHint")}
            href="/attendance"
          />
        )}
        {!isBoard && (
          <Stat
            label={t("stats.myDuesOpen")}
            value={String(openMyDues.length)}
            hint={
              openMyDues.length > 0
                ? formatEuro(
                    String(
                      openMyDues.reduce(
                        (sum, due) => sum + Number(due.amount),
                        0
                      )
                    ),
                    locale
                  )
                : t("stats.myDuesSettled")
            }
            href="/my"
          />
        )}
      </div>

      {openSessions && openSessions.data.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">
            {t("openSessions.title")}
          </h2>
          <div className="divide-y rounded-md border">
            {openSessions.data.map((s) => (
              <Link
                key={s.id}
                href={`/attendance/${s.id}`}
                className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm hover:bg-muted/50"
              >
                <div className="space-y-0.5">
                  <div className="font-medium">{s.title}</div>
                  <div className="text-xs text-muted-foreground">
                    {formatDateTime(s.opens_at, locale, timeZone)}
                    {s.location ? ` · ${s.location}` : ""}
                  </div>
                </div>
                <Badge variant="secondary">
                  {t("openSessions.records", { count: s.record_count })}
                </Badge>
              </Link>
            ))}
          </div>
        </section>
      )}
    </>
  )
}
