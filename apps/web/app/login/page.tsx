import { getTranslations } from "next-intl/server"

import { LoginForm } from "@/components/login-form"

export default async function LoginPage() {
  const t = await getTranslations("auth")

  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      <div className="flex flex-col gap-4 p-6 md:p-10">
        <div className="flex justify-center gap-2 md:justify-start">
          <span className="text-lg font-semibold tracking-tight">unefy</span>
        </div>
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-xs">
            <LoginForm />
          </div>
        </div>
      </div>
      <div className="relative hidden bg-muted lg:block">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/login-cover.svg"
          alt={t("coverAlt")}
          className="absolute inset-0 h-full w-full object-cover"
        />
      </div>
    </div>
  )
}
