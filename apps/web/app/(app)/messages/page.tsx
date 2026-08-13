import { notFound } from "next/navigation"
import Link from "next/link"
import { getTranslations } from "next-intl/server"

import { HeaderScrollTitle } from "@/components/layout/header-scroll-title"
import { MessagesTable } from "@/components/messages/messages-table"
import { buttonVariants } from "@/components/ui/button"
import { getClubTimeZone } from "@/lib/attendance"
import { listMessages } from "@/lib/messages"
import { PenLineIcon } from "lucide-react"

/**
 * What the club has sent.
 *
 * Board and above — the backend has no read access for members at all, and
 * that is deliberate: what went to whom is committee business, and a member's
 * own copy is in their inbox.
 */
export default async function MessagesPage() {
  const [t, timeZone, listed] = await Promise.all([
    getTranslations("messages"),
    getClubTimeZone(),
    listMessages().catch(() => null),
  ])
  if (listed === null) notFound()

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <HeaderScrollTitle title={t("title")} />
          <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">
            {t("description", { count: listed.meta.total })}
          </p>
        </div>
        <Link href="/messages/new" className={buttonVariants()}>
          <PenLineIcon />
          {t("compose")}
        </Link>
      </div>

      <MessagesTable messages={listed.data} timeZone={timeZone} />
    </>
  )
}
