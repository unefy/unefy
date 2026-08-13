import { notFound } from "next/navigation"
import Link from "next/link"
import { getLocale, getTranslations } from "next-intl/server"

import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"
import { RecipientsTable } from "@/components/messages/recipients-table"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { getClubTimeZone } from "@/lib/attendance"
import { getMessage, listRecipients } from "@/lib/messages"
import { formatDateTime } from "@/lib/time"

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-2xl tabular-nums">{value}</CardTitle>
      </CardHeader>
    </Card>
  )
}

/**
 * One round mail: what was written, and what became of every row.
 *
 * The recipient list is the reason this page exists — "who did not get it and
 * why" is the question a board member comes here with, and the counters above
 * are only the summary of it.
 */
export default async function MessagePage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const [t, locale, timeZone, message] = await Promise.all([
    getTranslations("messages"),
    getLocale(),
    getClubTimeZone(),
    getMessage(id).catch(() => null),
  ])
  if (message === null) notFound()

  const recipients = await listRecipients(id).catch(() => null)

  return (
    <>
      <div className="space-y-1">
        <HeaderScrollTitle title={message.subject} />
        <Link
          href="/messages"
          className="text-sm text-muted-foreground hover:underline"
        >
          {t("back")}
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">
          {message.subject}
        </h1>
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Badge variant="outline">{t(`kinds.${message.kind}`)}</Badge>
          <Badge
            variant={
              message.status === "failed"
                ? "destructive"
                : message.status === "done"
                  ? "secondary"
                  : "outline"
            }
          >
            {t(`statuses.${message.status}`)}
          </Badge>
          <span className="text-sm text-muted-foreground">
            {t("queuedAt", {
              when: formatDateTime(message.queued_at, locale, timeZone),
            })}
          </span>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label={t("counts.total")} value={String(message.recipient_count)} />
        <Stat label={t("counts.sent")} value={String(message.counts.sent ?? 0)} />
        <Stat
          label={t("counts.skipped")}
          value={String(message.counts.skipped ?? 0)}
        />
        <Stat
          label={t("counts.failed")}
          value={String(message.counts.failed ?? 0)}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("bodyTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          {/* The text as it was sent, line breaks and all — it is a letter,
              and nothing about it is markup. */}
          <p className="text-sm whitespace-pre-wrap">{message.body}</p>
        </CardContent>
      </Card>

      <section className="space-y-3">
        <h2 className="text-lg font-medium">{t("recipients.title")}</h2>
        {recipients === null ? (
          <p className="text-sm text-muted-foreground">
            {t("recipients.unavailable")}
          </p>
        ) : (
          <RecipientsTable recipients={recipients.data} timeZone={timeZone} />
        )}
      </section>
    </>
  )
}
