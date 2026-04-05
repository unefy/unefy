"use client"

import { useActionState } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { createClubAction, type ActionResult } from "@/actions/auth"

export function OnboardingForm() {
  const t = useTranslations("auth")
  const te = useTranslations("errors")
  const router = useRouter()

  const [state, formAction, pending] = useActionState<
    ActionResult<{ tenant_id: string; slug: string }> | undefined,
    FormData
  >(async (prev, formData) => {
    const result = await createClubAction(prev, formData)
    if (result.success) {
      router.push("/")
      router.refresh()
    } else {
      toast.error(te(result.error === "validation" ? "validation" : "unknown"))
    }
    return result
  }, undefined)

  const fieldError = state && !state.success ? state.fieldErrors?.club_name?.[0] : undefined

  return (
    <form action={formAction} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="club-name">{t("clubName")}</Label>
        <Input
          id="club-name"
          name="club_name"
          placeholder={t("clubNamePlaceholder")}
          required
          minLength={2}
          maxLength={255}
          aria-invalid={!!fieldError}
        />
        {fieldError && (
          <p className="text-destructive text-xs">{te("validation")}</p>
        )}
      </div>

      <Button type="submit" className="w-full" disabled={pending}>
        {pending ? t("creating") : t("createClubButton")}
      </Button>
    </form>
  )
}
