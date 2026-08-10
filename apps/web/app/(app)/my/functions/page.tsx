import { getTranslations } from "next-intl/server"

import { OwnFunctionsTable } from "@/components/my/own-functions-table"
import { listOwnFunctions } from "@/lib/functions"

/** The member's own terms of office, current and past. */
export default async function MyFunctionsPage() {
  const [t, functions] = await Promise.all([
    getTranslations("my.functions"),
    listOwnFunctions().catch(() => []),
  ])

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium text-muted-foreground">
        {t("heading")}
      </h2>
      <OwnFunctionsTable functions={functions} />
    </section>
  )
}
