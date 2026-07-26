"use client"

import { useRouter } from "next/navigation"
import { useTranslations, useLocale } from "next-intl"
import { Badge } from "@/components/ui/badge"
import { SectionHeading } from "@/components/layout/section-heading"
import { useEvents } from "@/hooks/use-events"
import { formatDate } from "@/lib/date"

interface CompetitionEventsSectionProps {
  competitionId: string
}

export function CompetitionEventsSection({
  competitionId,
}: CompetitionEventsSectionProps) {
  const t = useTranslations("competitions")
  const te = useTranslations("events")
  const locale = useLocale()
  const router = useRouter()

  const { data, isLoading } = useEvents({
    competition_id: competitionId,
    per_page: 100,
    sort_order: "asc",
  })

  const events = data?.data ?? []

  return (
    <div>
      <SectionHeading
        title={t("linkedEvents")}
        description={t("linkedEventsDescription")}
      />

      {isLoading ? (
        <div className="h-32 animate-pulse rounded-xl bg-muted" />
      ) : events.length === 0 ? (
        <p className="text-muted-foreground py-6 text-center text-sm">
          {t("noLinkedEvents")}
        </p>
      ) : (
        <ul className="divide-y rounded-xl border">
          {events.map((event) => (
            <li key={event.id}>
              <button
                type="button"
                onClick={() => router.push(`/events/${event.id}`)}
                className="hover:bg-muted/50 flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium">{event.title}</p>
                  <p className="text-muted-foreground truncate text-xs">
                    {formatDate(event.starts_at, locale)}
                    {event.location ? ` · ${event.location}` : ""}
                  </p>
                </div>
                {event.status === "cancelled" && (
                  <Badge variant="outline">{te("status_cancelled")}</Badge>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
