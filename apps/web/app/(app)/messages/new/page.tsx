import { notFound } from "next/navigation"
import Link from "next/link"
import { getTranslations } from "next-intl/server"

import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"
import { ComposeForm } from "@/components/messages/compose-form"
import { getSession } from "@/lib/auth"
import { getClubTimeZone } from "@/lib/attendance"
import { listEvents } from "@/lib/events"
import { listActiveFunctions } from "@/lib/functions"

/** The club's own year, not the browser's — see the dues page. */
function clubYear(timeZone: string): number {
  return Number(new Intl.DateTimeFormat("en-CA", { timeZone }).format(new Date()).slice(0, 4))
}

export default async function ComposeMessagePage() {
  const [t, session, timeZone, functions, events] = await Promise.all([
    getTranslations("messages"),
    getSession(),
    getClubTimeZone(),
    listActiveFunctions().catch(() => []),
    listEvents({ perPage: 50 }).catch(() => null),
  ])
  if (!session) notFound()

  return (
    <>
      <div className="space-y-1">
        <HeaderScrollTitle title={t("compose")} />
        <Link
          href="/messages"
          className="text-sm text-muted-foreground hover:underline"
        >
          {t("back")}
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">{t("compose")}</h1>
        <p className="text-sm text-muted-foreground">{t("composeHint")}</p>
      </div>

      <ComposeForm
        functions={functions}
        events={events?.data ?? []}
        currentYear={clubYear(timeZone)}
        ownEmail={session.user.email}
      />
    </>
  )
}
