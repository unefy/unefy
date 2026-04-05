"use client"

import { useActionState } from "react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { requestMagicLinkAction, type ActionResult } from "@/actions/auth"
import { API_URL } from "@/lib/constants"

export function LoginForm() {
  const t = useTranslations("auth")
  const te = useTranslations("errors")

  const [state, formAction, pending] = useActionState<
    ActionResult | undefined,
    FormData
  >(async (prev, formData) => {
    const result = await requestMagicLinkAction(prev, formData)
    if (!result.success) {
      toast.error(te("unknown"))
    }
    return result
  }, undefined)

  // Google OAuth must be a top-level browser redirect (cross-origin flow),
  // so it intentionally does not go through a Server Action.
  function handleGoogleSignIn() {
    window.location.href = `${API_URL}/api/v1/auth/oauth/google`
  }

  const sent = state?.success === true

  return (
    <div className="space-y-4">
      <Button onClick={handleGoogleSignIn} variant="outline" className="w-full">
        {t("continueWithGoogle")}
      </Button>

      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-background text-muted-foreground px-2">
            {t("or")}
          </span>
        </div>
      </div>

      {!sent ? (
        <form action={formAction} className="space-y-3">
          <Input
            type="email"
            name="email"
            placeholder={t("emailAddress")}
            required
          />
          <Button type="submit" className="w-full" disabled={pending}>
            {t("sendMagicLink")}
          </Button>
        </form>
      ) : (
        <p className="text-muted-foreground text-center text-sm">
          {t("checkEmail")}
        </p>
      )}
    </div>
  )
}
