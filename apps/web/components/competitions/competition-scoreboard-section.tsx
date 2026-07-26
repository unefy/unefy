"use client"

import { useMemo } from "react"
import Link from "next/link"
import { useTranslations, useLocale } from "next-intl"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { SectionHeading } from "@/components/layout/section-heading"
import { useScoreboard } from "@/hooks/use-competitions"
import { useMembers } from "@/hooks/use-members"

interface CompetitionScoreboardSectionProps {
  competitionId: string
}

export function CompetitionScoreboardSection({
  competitionId,
}: CompetitionScoreboardSectionProps) {
  const t = useTranslations("competitions")
  const locale = useLocale()

  const { data, isLoading } = useScoreboard(competitionId)
  const { data: membersData } = useMembers({ per_page: 100 })

  const memberNames = useMemo(() => {
    const map = new Map<string, string>()
    for (const m of membersData?.data ?? []) {
      map.set(m.id, `${m.first_name} ${m.last_name}`)
    }
    return map
  }, [membersData])

  const rows = data?.data ?? []

  return (
    <div>
      <SectionHeading
        title={t("scoreboard")}
        description={t("scoreboardDescription")}
      />

      {isLoading ? (
        <div className="h-32 animate-pulse rounded-xl bg-muted" />
      ) : rows.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          {t("noScoreboard")}
        </p>
      ) : (
        <div className="rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">#</TableHead>
                <TableHead>{t("member")}</TableHead>
                <TableHead className="text-right">{t("totalScore")}</TableHead>
                <TableHead className="text-right">{t("entryCount")}</TableHead>
                <TableHead className="text-right">
                  {t("averageScore")}
                </TableHead>
                <TableHead className="text-right">{t("bestScore")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.member_id}>
                  <TableCell className="text-muted-foreground">
                    {row.rank}
                  </TableCell>
                  <TableCell>
                    <Link
                      href={`/members/${row.member_id}`}
                      className="font-medium hover:underline"
                    >
                      {memberNames.get(row.member_id) ?? t("unknownMember")}
                    </Link>
                  </TableCell>
                  <TableCell className="text-right font-medium tabular-nums">
                    {row.total_score.toLocaleString(locale)}{" "}
                    <span className="font-normal text-muted-foreground">
                      {data?.scoring_unit}
                    </span>
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground tabular-nums">
                    {row.entry_count}
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground tabular-nums">
                    {row.average_score.toLocaleString(locale, {
                      maximumFractionDigits: 2,
                    })}
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground tabular-nums">
                    {row.best_score.toLocaleString(locale)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
