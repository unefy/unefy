import { notFound } from "next/navigation"
import { getTranslations } from "next-intl/server"

import { ConsentPanel } from "@/components/members/consent-panel"
import { MemberExport } from "@/components/members/member-export"
import { getMemberConsents } from "@/lib/consents"

/** A member's consents, plus the Art. 15 bundle for a request on paper. */
export default async function MemberConsentsPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const [t, { id }] = await Promise.all([getTranslations("consents"), params])

  const overview = await getMemberConsents(id).catch(() => null)
  if (!overview) notFound()

  return (
    <div className="space-y-6">
      <ConsentPanel overview={overview} memberId={id} />

      <section className="space-y-2 rounded-lg border p-4">
        <h2 className="text-sm font-medium">{t("export.title")}</h2>
        <p className="max-w-2xl text-sm text-muted-foreground">
          {t("export.description")}
        </p>
        <MemberExport memberId={id} />
      </section>
    </div>
  )
}
