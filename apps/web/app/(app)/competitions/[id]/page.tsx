import Link from "next/link"
import { notFound } from "next/navigation"
import { getLocale, getTranslations } from "next-intl/server"

import { deleteCompetitionAction } from "@/actions/competitions"
import { CompetitionDialog } from "@/components/competitions/competition-dialog"
import { RoundsPanel } from "@/components/competitions/rounds-panel"
import { ScoreboardTable } from "@/components/competitions/scoreboard-table"
import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ConfirmAction } from "@/components/ui/confirm-action"
import { getClubTimeZone } from "@/lib/attendance"
import { getSession } from "@/lib/auth"
import {
  getCompetition,
  getScoreboard,
  listCompetitionSessions,
} from "@/lib/competitions"
import { formatDate } from "@/lib/time"
import { ArrowLeftIcon, Trash2Icon } from "lucide-react"

const BOARD_ROLES = ["owner", "admin", "board"]
const DELETE_ROLES = ["owner", "admin"]

function Fact({
  label,
  value,
  children,
}: {
  label: string
  value?: string | null
  children?: React.ReactNode
}) {
  return (
    <div className="space-y-1">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm">{children ?? (value?.trim() ? value : "—")}</dd>
    </div>
  )
}

export default async function CompetitionPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const [t, locale, timeZone, session, { id }] = await Promise.all([
    getTranslations("competitions"),
    getLocale(),
    getClubTimeZone(),
    getSession(),
    params,
  ])

  const competition = await getCompetition(id).catch(() => null)
  if (!competition) notFound()

  const canManage = BOARD_ROLES.includes(session?.role ?? "")

  // Rounds are board-only in the backend; a member still gets the ranking,
  // which is the part a competition exists to publish.
  const [scoreboard, rounds] = await Promise.all([
    getScoreboard(id).catch(() => ({
      rows: [],
      scoring_mode: competition.scoring_mode,
      scoring_unit: competition.scoring_unit,
    })),
    canManage ? listCompetitionSessions(id).catch(() => []) : [],
  ])

  return (
    <>
      <div className="space-y-3">
        <Link
          href="/competitions"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeftIcon className="size-4" />
          {t("detail.back")}
        </Link>

        <div className="flex flex-wrap items-center gap-3">
          <HeaderScrollTitle title={competition.name} />
          <h1 className="text-2xl font-semibold tracking-tight">
            {competition.name}
          </h1>
          <Badge variant="secondary">
            {t(`types.${competition.competition_type}`)}
          </Badge>

          {canManage && (
            <div className="ms-auto flex flex-wrap items-center gap-2">
              <CompetitionDialog competition={competition} />
              {DELETE_ROLES.includes(session?.role ?? "") && (
                <ConfirmAction
                  trigger={
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={t("detail.delete")}
                    >
                      <Trash2Icon className="text-destructive" />
                    </Button>
                  }
                  title={t("deleteDialog.title")}
                  description={t("deleteDialog.description")}
                  confirmLabel={t("deleteDialog.confirm")}
                  successMessage={t("toasts.deleted")}
                  redirectTo="/competitions"
                  action={deleteCompetitionAction.bind(null, competition.id)}
                />
              )}
            </div>
          )}
        </div>
      </div>

      <dl className="grid gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-4">
        <Fact
          label={t("columns.period")}
          value={
            competition.end_date && competition.end_date !== competition.start_date
              ? `${formatDate(competition.start_date, locale, timeZone)} – ${formatDate(competition.end_date, locale, timeZone)}`
              : formatDate(competition.start_date, locale, timeZone)
          }
        />
        <Fact label={t("fields.scoringUnit")} value={competition.scoring_unit} />
        <Fact
          label={t("fields.scoringMode")}
          value={t(`modes.${competition.scoring_mode}`)}
        />
        <Fact label={t("columns.disciplines")}>
          {competition.disciplines?.length ? (
            <span className="flex flex-wrap gap-1">
              {competition.disciplines.map((discipline) => (
                <Badge key={discipline} variant="outline">
                  {discipline}
                </Badge>
              ))}
            </span>
          ) : (
            "—"
          )}
        </Fact>
        {competition.description && (
          <div className="space-y-1 sm:col-span-2 lg:col-span-4">
            <dt className="text-xs text-muted-foreground">
              {t("fields.description")}
            </dt>
            <dd className="text-sm whitespace-pre-line">
              {competition.description}
            </dd>
          </div>
        )}
      </dl>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">
          {t("scoreboard.title")}
        </h2>
        <ScoreboardTable
          scoreboard={scoreboard}
          disciplines={competition.disciplines ?? []}
        />
      </section>

      {canManage && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">
            {t("rounds.title", { count: rounds.length })}
          </h2>
          <RoundsPanel
            competitionId={competition.id}
            sessions={rounds}
            timeZone={timeZone}
            canManage={canManage}
            canDelete={DELETE_ROLES.includes(session?.role ?? "")}
          />
        </section>
      )}
    </>
  )
}
