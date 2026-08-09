import Link from "next/link"
import { notFound } from "next/navigation"
import { getLocale, getTranslations } from "next-intl/server"

import { EntriesPanel } from "@/components/competitions/entries-panel"
import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"
import { Badge } from "@/components/ui/badge"
import { getClubTimeZone } from "@/lib/attendance"
import { getSession } from "@/lib/auth"
import {
  getCompetition,
  listCompetitionSessions,
  listEntries,
} from "@/lib/competitions"
import { listMembers } from "@/lib/members"
import { formatDate } from "@/lib/time"
import { ArrowLeftIcon, CalendarIcon } from "lucide-react"

const BOARD_ROLES = ["owner", "admin", "board"]
const DELETE_ROLES = ["owner", "admin"]

export default async function RoundPage({
  params,
}: {
  params: Promise<{ id: string; roundId: string }>
}) {
  const [t, locale, timeZone, session, { id, roundId }] = await Promise.all([
    getTranslations("competitions"),
    getLocale(),
    getClubTimeZone(),
    getSession(),
    params,
  ])

  // Rounds and their results are board work in the backend; asking as a member
  // would only produce a 403 and an empty page.
  if (!BOARD_ROLES.includes(session?.role ?? "")) notFound()

  const competition = await getCompetition(id).catch(() => null)
  if (!competition) notFound()

  // There is no single-round endpoint — the list is the only way in.
  const rounds = await listCompetitionSessions(id).catch(() => [])
  const round = rounds.find((candidate) => candidate.id === roundId)
  if (!round) notFound()

  const [entries, members] = await Promise.all([
    listEntries(id, roundId).catch(() => []),
    // Results carry member ids only; the names come from the register.
    listMembers({ perPage: 100 })
      .then((result) => result.data)
      .catch(() => []),
  ])

  const memberNames = Object.fromEntries(
    members.map((member) => [
      member.id,
      `${member.first_name} ${member.last_name}`,
    ])
  )

  return (
    <>
      <div className="space-y-3">
        <Link
          href={`/competitions/${id}`}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeftIcon className="size-4" />
          {competition.name}
        </Link>

        <div className="flex flex-wrap items-center gap-3">
          <HeaderScrollTitle title={round.name ?? t("rounds.unnamed")} />
          <h1 className="text-2xl font-semibold tracking-tight">
            {round.name ?? t("rounds.unnamed")}
          </h1>
          <span className="text-sm text-muted-foreground">
            {formatDate(round.date, locale, timeZone)}
          </span>
          {round.discipline && (
            <Badge variant="outline">{round.discipline}</Badge>
          )}
          {round.event_id && (
            <Badge
              variant="outline"
              className="gap-1"
              render={
                <Link href={`/events/${round.event_id}`}>
                  <CalendarIcon className="size-3" />
                  {t("rounds.inCalendar")}
                </Link>
              }
            />
          )}
          {round.location && (
            <span className="text-sm text-muted-foreground">
              {round.location}
            </span>
          )}
        </div>
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">
          {t("entries.title", { count: entries.length })}
        </h2>
        <EntriesPanel
          competitionId={id}
          sessionId={roundId}
          entries={entries}
          memberNames={memberNames}
          scoreUnit={competition.scoring_unit}
          canManage
          canDelete={DELETE_ROLES.includes(session?.role ?? "")}
        />
      </section>
    </>
  )
}
