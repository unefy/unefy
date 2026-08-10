import { getTranslations } from "next-intl/server"

import { DuesTable } from "@/components/dues/dues-table"
import { getClubTimeZone } from "@/lib/attendance"
import { listMyDues } from "@/lib/dues"

/** The club's own today, not the browser's — see `lib/time`. */
function clubToday(timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone }).format(new Date())
}

export default async function MyDuesPage() {
  const [t, timeZone] = await Promise.all([
    getTranslations("my"),
    getClubTimeZone(),
  ])

  // Empty rather than an error for an unlinked account: the endpoint 404s, and
  // "you owe nothing" is the truthful reading of that.
  const dues = await listMyDues().catch(() => [])

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium text-muted-foreground">{t("dues")}</h2>
      <DuesTable dues={dues} timeZone={timeZone} today={clubToday(timeZone)} />
    </section>
  )
}
