import { getTranslations } from "next-intl/server"

import { ConsentPanel } from "@/components/members/consent-panel"
import { MemberExport } from "@/components/members/member-export"
import { getOwnConsents } from "@/lib/consents"

/**
 * The member's own view of what the club may do with their data, and the copy
 * of it they are entitled to.
 *
 * Self-service on purpose: Art. 15 is the member's right, and putting the
 * board between a person and their own data serves nobody.
 */
export default async function MyDataPage() {
  const [t, overview] = await Promise.all([
    getTranslations("consents"),
    getOwnConsents().catch(() => null),
  ])

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-sm font-medium text-muted-foreground">
          {t("myTitle")}
        </h2>
        <p className="max-w-2xl text-sm text-muted-foreground">
          {t("myDescription")}
        </p>
      </div>

      {overview ? (
        <ConsentPanel overview={overview} />
      ) : (
        <p className="text-sm text-muted-foreground">{t("noMemberRecord")}</p>
      )}

      <section className="space-y-2 rounded-lg border p-4">
        <h2 className="text-sm font-medium">{t("export.title")}</h2>
        <p className="max-w-2xl text-sm text-muted-foreground">
          {t("export.ownDescription")}
        </p>
        <MemberExport />
      </section>
    </div>
  )
}
