"use client"

import { useTransition } from "react"
import { useTranslations } from "next-intl"

import { stopImpersonationAction } from "@/actions/admin"
import { Button } from "@/components/ui/button"
import type { Impersonator } from "@/lib/auth"
import { EyeIcon } from "lucide-react"

/**
 * Always-visible reminder that the current session is impersonated.
 *
 * Deliberately loud and non-dismissible: the failure mode this guards against
 * is an admin forgetting whose account they are in and changing real club data
 * by accident.
 */
export function ImpersonationBanner({
  impersonator,
  userName,
}: {
  impersonator: Impersonator
  userName: string
}) {
  const t = useTranslations("admin.banner")
  const [pending, startTransition] = useTransition()

  return (
    <div
      role="status"
      className="flex flex-wrap items-center justify-between gap-2 bg-destructive px-4 py-2 text-sm text-white"
    >
      <span className="flex items-center gap-2">
        <EyeIcon className="size-4 shrink-0" />
        {t("message", { user: userName, admin: impersonator.email })}
      </span>
      <Button
        size="sm"
        variant="outline"
        disabled={pending}
        className="border-white/40 bg-transparent text-white hover:bg-white/10"
        onClick={() =>
          startTransition(async () => {
            await stopImpersonationAction()
          })
        }
      >
        {pending ? t("stopping") : t("stop")}
      </Button>
    </div>
  )
}
