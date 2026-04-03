import { redirect } from "next/navigation"
import { getTranslations } from "next-intl/server"
import { getSession } from "@/lib/auth"
import { OnboardingForm } from "@/components/auth/onboarding-form"

export default async function OnboardingPage() {
  const session = await getSession()
  const t = await getTranslations("auth")

  if (!session) {
    redirect("/login")
  }

  if (!session.needs_onboarding) {
    redirect("/")
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-2 text-center">
          <h1 className="text-2xl font-bold">{t("welcome")}</h1>
          <p className="text-muted-foreground text-sm">
            {t("createClub")}
          </p>
        </div>
        <OnboardingForm userName={session.user.name} />
      </div>
    </div>
  )
}
