"use client"

import { useActionState } from "react"
import { useTranslations } from "next-intl"
import { useSearchParams } from "next/navigation"

import { requestMagicLinkAction, type ActionResult } from "@/actions/auth"
import { LOGIN_NEXT_COOKIE, safeNextPath } from "@/lib/next-path"
import { Button } from "@/components/ui/button"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldSeparator,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { API_URL } from "@/lib/constants"
import { cn } from "@/lib/utils"

export function LoginForm({
  className,
  ...props
}: React.ComponentProps<"form">) {
  const t = useTranslations("auth")
  const params = useSearchParams()
  const nextPath = safeNextPath(params.get("next"))

  // The backend redirects here with `?error=` when a sign-in attempt fails —
  // an expired magic link, or a refused Google callback. Only known codes are
  // rendered; anything else would let a crafted URL put arbitrary text on the
  // login page.
  const redirectError = params.get("error")
  const linkError =
    redirectError === "link_invalid" || redirectError === "oauth_failed"
      ? redirectError
      : null
  const [state, formAction, pending] = useActionState<
    ActionResult | undefined,
    FormData
  >(requestMagicLinkAction, undefined)

  // Google OAuth must be a top-level browser redirect (cross-origin flow),
  // so it intentionally does not go through a Server Action.
  function handleGoogleSignIn() {
    // The backend callback always lands on the app home, so park the intended
    // target in a short-lived cookie for the proxy to pick up afterwards.
    if (nextPath) {
      document.cookie = `${LOGIN_NEXT_COOKIE}=${encodeURIComponent(nextPath)}; path=/; max-age=600; samesite=lax`
    }
    window.location.href = `${API_URL}/api/v1/auth/oauth/google`
  }

  const sent = state?.success === true
  const error = state?.success === false ? state.error : undefined

  return (
    <form
      action={formAction}
      className={cn("flex flex-col gap-6", className)}
      {...props}
    >
      <FieldGroup>
        <div className="flex flex-col items-center gap-1 text-center">
          <h1 className="text-2xl font-bold">{t("signInTitle")}</h1>
          <p className="text-sm text-balance text-muted-foreground">
            {t("signInDescription")}
          </p>
        </div>

        {linkError && (
          <FieldError className="text-center">
            {t(`errors.${linkError}`)}
          </FieldError>
        )}

        {sent ? (
          <FieldDescription className="text-center">
            {t("checkEmail")}
          </FieldDescription>
        ) : (
          <>
            <Field data-invalid={error ? true : undefined}>
              <FieldLabel htmlFor="email">{t("emailLabel")}</FieldLabel>
              <Input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                placeholder={t("emailPlaceholder")}
                aria-invalid={error ? true : undefined}
                required
              />
              {error && <FieldError>{t(`errors.${error}`)}</FieldError>}
            </Field>
            <Field>
              <Button type="submit" disabled={pending}>
                {pending ? t("sending") : t("sendMagicLink")}
              </Button>
            </Field>
          </>
        )}

        <FieldSeparator>{t("or")}</FieldSeparator>

        <Field>
          <Button variant="outline" type="button" onClick={handleGoogleSignIn}>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.07 5.07 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1Z"
                fill="#4285F4"
              />
              <path
                d="M12 23c2.97 0 5.46-.98 7.28-2.65l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z"
                fill="#34A853"
              />
              <path
                d="M5.84 14.11a6.6 6.6 0 0 1 0-4.22V7.05H2.18a11 11 0 0 0 0 9.9l3.66-2.84Z"
                fill="#FBBC05"
              />
              <path
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1a11 11 0 0 0-9.82 6.05l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38Z"
                fill="#EA4335"
              />
            </svg>
            {t("continueWithGoogle")}
          </Button>
        </Field>
      </FieldGroup>
    </form>
  )
}
