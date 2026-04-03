import { getTranslations } from "next-intl/server"
import { LoginForm } from "@/components/auth/login-form"

export default async function LoginPage() {
  const t = await getTranslations("auth")

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-2 text-center">
          <h1 className="text-2xl font-bold">unefy</h1>
          <p className="text-muted-foreground text-sm">
            {t("signInDescription")}
          </p>
        </div>
        <LoginForm />
      </div>
    </div>
  )
}
