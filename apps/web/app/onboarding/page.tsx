import { redirect } from "next/navigation"
import { getTranslations } from "next-intl/server"

import { OnboardingForm } from "@/components/onboarding/onboarding-form"
import { getSession } from "@/lib/auth"
import { listAvailableSports } from "@/lib/sports"

export default async function OnboardingPage() {
  const session = await getSession()
  if (!session) {
    redirect("/login")
  }

  // Reachable with a tenant too — a user may found a second club — so this
  // page must not assume `needs_onboarding`.
  const [t, sports] = await Promise.all([
    getTranslations("onboarding"),
    listAvailableSports(),
  ])

  return (
    <div className="flex min-h-svh items-center justify-center p-6">
      <div className="w-full max-w-lg space-y-8">
        <div className="space-y-2 text-center">
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("title")}
          </h1>
          <p className="text-sm text-muted-foreground">{t("description")}</p>
        </div>

        {sports.length === 0 ? (
          // Without a sport there is nothing to seed the club from, and the
          // form would submit an unsatisfiable payload.
          <p className="rounded-md border border-destructive/40 p-4 text-sm text-destructive">
            {t("noSports")}
          </p>
        ) : (
          <OnboardingForm sports={sports} />
        )}
      </div>
    </div>
  )
}
